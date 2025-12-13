<?php
declare(strict_types=1);

require 'vendor/autoload.php';

require_once __DIR__ . '/buildToken.php';
require_once __DIR__ . '/checkToken.php';

use Lcobucci\JWT\Encoding\JoseEncoder;
use Lcobucci\JWT\Token\Parser;
use Lcobucci\JWT\Signer\Key\InMemory;


header('Content-Type: application/json');


// $key   = InMemory::plainText(random_bytes(32));
$config = parse_ini_file('/var/www/files/platane/config.ini', true);
if (!$config || !isset($config['JWT']['key']) || !isset($config['JWT']['relatedTo']) || !isset($config['JWT']['issuedBy'])) {
    http_response_code(500);
    echo json_encode(["error" => "JWT config invalid"]);
    exit;
}
$key = InMemory::plainText($config['JWT']['key']);
$relatedTo = $config['JWT']['relatedTo'];
$issuedBy = $config['JWT']['issuedBy'];

$devicesFile = '/var/www/files/platane/devices.json';
if (file_exists($devicesFile)) {
    $json = file_get_contents($devicesFile);
    $devices = json_decode($json, true);
} else {
    http_response_code(500);
    echo json_encode(["error" => "Devices file not found"]);
    exit;
}

$audioDir = __DIR__ . "/audio/";


// ===== INPUT =====
$input = json_decode(file_get_contents("php://input"), true);
if (!$input) {
    http_response_code(400);
    echo json_encode(["error" => "Invalid JSON"]);
    exit;
}

$command = $input['command'] ?? null;

// 1) JOIN REQUEST
if ($command === "join" && isset($input['id'])) {
    $id = $input['id'];
    $identifiedBy = $id;
    if (!isset($devices[$id])) {
        http_response_code(401);
        echo json_encode(["status" => "not authorized0"]);
        exit;
    }
    $devKey = $devices[$id];
    $identifiedBy = "Sensor_" . $id;

    $challenge = bin2hex(openssl_random_pseudo_bytes(16));
    $iv = bin2hex(openssl_random_pseudo_bytes(16));
    $sessionId = bin2hex(random_bytes(8)); // unique handle for this challenge

    file_put_contents("/tmp/challenge_{$id}_{$sessionId}.json", json_encode([
        "challenge" => $challenge,
        "iv" => $iv,
        "time" => time()
    ]));

    echo json_encode([
        "session" => $sessionId,   // send back to client
        "challenge" => $challenge,
        "iv" => $iv
    ]);

    exit;
}

// 2) CHALLENGE RESPONSE
if ($command === "challenge" && isset($input['id'], $input['session'], $input['challenge'])) {
    $id = $input['id'];
    $sessionId = $input['session'];

    $filePath = "/tmp/challenge_{$id}_{$sessionId}.json";
    if (!file_exists($filePath)) {
        http_response_code(401);
        echo json_encode(["status" => "not authorized2"]);
        exit;
    }
    $stored = json_decode(@file_get_contents($filePath), true);

    // Same expiry check
    if (!$stored || time() - $stored['time'] > 60) {
        http_response_code(401);
        echo json_encode(["status" => "not authorized3"]);
        exit;
    }

    $devKey = $devices[$id];
    $keyBin = hex2bin($devKey);
    $ivBin = hex2bin($stored['iv']);
    $identifiedBy = "Sensor_" . $id;

    $expected = openssl_encrypt(
        hex2bin($stored['challenge']),
        "AES-128-CBC", 
        $keyBin,
        OPENSSL_RAW_DATA | OPENSSL_ZERO_PADDING,  // micropython has no padding
        $ivBin
    );
    // micropython has no padding => cut if present
    //$expected = substr($expected, 0, 16);

    if (hash_equals(bin2hex($expected), $input['challenge'])) {
        $now = new DateTimeImmutable();
        $token = createToken($key, $identifiedBy, $relatedTo, $issuedBy);
        echo json_encode(["token" => $token]);
    } else {
        http_response_code(401);
        echo json_encode(["status" => "not authorized4: " . bin2hex($expected) ]);
    }
    exit;
}

// raw data to wav for wav format
/**
 * Create a WAV file from raw PCM data.
 *
 * @param string $pcmData   Raw audio bytes (little‑endian signed integer samples)
 * @param int    $sampleRate Sample rate in Hz (e.g., 8000)
 * @param int    $bitsPerSample Bits per sample (8 or 16 are typical)
 * @return string            Complete WAV file contents (header + PCM)
 */
function pcmToWav(string $pcmData, int $sampleRate = 8000, int $bitsPerSample = 16): string
{
    // ------------------------------------------------------------
    // 1️⃣  Basic parameters
    // ------------------------------------------------------------
    $numChannels   = 1;                     // mono
    $byteRate      = ($sampleRate * $numChannels * $bitsPerSample) / 8;
    $blockAlign    = ($numChannels * $bitsPerSample) / 8;
    $subchunk2Size = strlen($pcmData);      // size of the raw audio data

    // ------------------------------------------------------------
    // 2️⃣  Build the RIFF header (44 bytes total)
    // ------------------------------------------------------------
    $header = '';
    $header .= pack('A4', 'RIFF');                         // ChunkID
    $header .= pack('V', 36 + $subchunk2Size);             // ChunkSize = 36 + SubChunk2Size
    $header .= pack('A4', 'WAVE');                         // Format

    // fmt sub‑chunk
    $header .= pack('A4', 'fmt ');                         // Subchunk1ID
    $header .= pack('V', 16);                              // Subchunk1Size (PCM = 16)
    $header .= pack('v', 1);                               // AudioFormat (1 = PCM)
    $header .= pack('v', $numChannels);                   // NumChannels
    $header .= pack('V', $sampleRate);                    // SampleRate
    $header .= pack('V', $byteRate);                      // ByteRate
    $header .= pack('v', $blockAlign);                    // BlockAlign
    $header .= pack('v', $bitsPerSample);                 // BitsPerSample

    // data sub‑chunk
    $header .= pack('A4', 'data');                         // Subchunk2ID
    $header .= pack('V', $subchunk2Size);                  // Subchunk2Size

    // ------------------------------------------------------------
    // 3️⃣  Concatenate header + raw PCM and return
    // ------------------------------------------------------------
    return $header . $pcmData;
}



// 3) DATA PACKET
if ($command === "data" && isset($input['id']) && isset($input['token'], $input['data'])) {
    $token = $input['token'];
    $identifiedBy = "Sensor_" . $input['id'];
    try {
        if (!validateToken($token, $relatedTo, $issuedBy, $identifiedBy, $key)) {
            throw new Exception("Invalid token");
        }
    } catch (Exception $e) {
        http_response_code(401);
        echo json_encode(["status" => "not authorized5"]);
        exit;
    }

    $parser = new Parser(new JoseEncoder());
    try {
        $parsedToken = $parser->parse($token);
    } catch (Exception $e) {
        http_response_code(401);
        echo json_encode(["status" => "not authorized6"]);
        exit;
    }
    $id = $parsedToken->claims()->get('sensor');

    $uuid = uniqid($identifiedBy . "_", true);
    try {
        $audioFormat = $input['format'] ?? 'adpcm';
        $audioData = base64_decode($input['data'], true);
        if ($audioData === false) {
            http_response_code(400);
            echo json_encode(["status" => "data invalid"]);
            exit;
        }
        // Check size limit 512 KB
        if (strlen($audioData) > 512 * 1024) {
            http_response_code(401);
            echo json_encode(["status" => "not authorized7"]);
            exit;
        }
        if ($audioFormat == "wav") {
            // convert raw pcm to wav
            $audioData = pcmToWav($audioData, 8000, 16);
        }
        $audioFile = $audioDir . $uuid . ($audioFormat == "adpcm" ? ".adpcm" : ".wav");
        if (file_put_contents($audioFile, $audioData) === false) {
            http_response_code(500);
            echo json_encode(["error" => "Failed to write audio file"]);
            exit;
        }
        // simulate some processing by saving a lock file
        $lockFile = $audioDir . $uuid . ".lock";
        if (file_put_contents($lockFile, "locked") === false) {
            http_response_code(500);
            echo json_encode(["error" => "Failed to write lock file"]);
            exit;
        }
    } catch (Exception $e) {
        http_response_code(500);
        echo json_encode(["error" => "Failed to save data"]);
        exit;
    }

    echo json_encode(["uuid" => $uuid]);
    exit;
}

http_response_code(400);
echo json_encode(["error" => "Unknown command"]);
