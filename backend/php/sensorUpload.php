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
        //"AES-256-CBC",  // was 128
        "AES-128-CBC",  // was 128
        $keyBin,
        OPENSSL_RAW_DATA,
        $ivBin
    );

    if (hash_equals(bin2hex($expected), $input['challenge'])) {
        $now = new DateTimeImmutable();
        $token = createToken($key, $identifiedBy, $relatedTo, $issuedBy);
        echo json_encode(["token" => $token]);
    } else {
        http_response_code(401);
        echo json_encode(["status" => "not authorized4"]);
    }
    exit;
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
        $audioFile = $audioDir . $uuid . ".adpcm";
        if (file_put_contents($audioFile, $audioData) === false) {
            http_response_code(500);
            echo json_encode(["error" => "Failed to write audio file"]);
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
