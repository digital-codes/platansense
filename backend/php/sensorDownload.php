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


$audioDir = __DIR__ . "/audio/";
$chunkSize = 4096; // or any other chunk size you want


// ===== INPUT =====
$input = json_decode(file_get_contents("php://input"), true);
if (!$input) {
    http_response_code(400);
    echo json_encode(["error" => "Invalid JSON"]);
    exit;
}

$command = $input['command'] ?? null;

// 1) CHECK REQUEST
if ($command === "check" && isset($input['name']) && isset($input['id']) && isset($input['token'])) {
    $token = $input['token'];
    $identifiedBy = "Sensor_" . $input['id'];
    try {
        if (!validateToken($token, $relatedTo, $issuedBy, $identifiedBy, $key)) {
            throw new Exception("Invalid token");
        }
    } catch (Exception $e) {
        http_response_code(401);
        echo json_encode(["status" => "not authorized"]);
        exit;
    }

    $name = $input['name'] ?? '';
    // keep only the filename (basename) — strips any path components
    $name = basename((string)$name);
    // remove any null bytes just in case
    $name = str_replace("\0", '', $name);

    if ($name === '' || strlen($name) > 255) {
        http_response_code(400);
        echo json_encode(["status" => "invalid name"]);
        exit;
    }

    // check lock file exists only if $name starts with "Sensor"
    if (str_starts_with($name, "Sensor")) {
        $filePath = $audioDir . $name . ".lock";
        if (!file_exists($filePath)) {
            http_response_code(404);
            echo json_encode(["status" => "file not found " . $name]);
            exit;
        }
    }

    // then check audio file exists
    $filePath = $audioDir . $name . "_chat.adpcm";
    if (!file_exists($filePath)) {
        http_response_code(408);
        echo json_encode(["status" => "file not ready. retry later"]);
        exit;
    }

    // remove the lock file to indicate download can start
    unlink($audioDir . $name . ".lock");    

    $fileSize = filesize($filePath);
    $numChunks = (int)ceil($fileSize / $chunkSize);

    echo json_encode([
        "status" => "ready",
        "size" => $fileSize,
        "chunks" => $numChunks,
        "chunksize" => $chunkSize
    ]);

    exit;
}

// 2) DOWN RESPONSE
if ($command === "down" && isset($input['name']) && isset($input['chunk']) && isset($input['id']) && isset($input['token'])) {
    $token = $input['token'];
    $identifiedBy = "Sensor_" . $input['id'];
    try {
        if (!validateToken($token, $relatedTo, $issuedBy, $identifiedBy, $key)) {
            throw new Exception("Invalid token");
        }
    } catch (Exception $e) {
        http_response_code(401);
        echo json_encode(["status" => "not authorized"]);
        exit;
    }

    $name = $input['name'];
    $chunk = (int)$input['chunk'];

    $filePath = $audioDir . $name . "_chat.adpcm";
    if (!file_exists($filePath)) {
        http_response_code(404);
        echo json_encode(["status" => "file not found"]);
        exit;
    }

    $fileSize = filesize($filePath);
    $numChunks = (int)ceil($fileSize / $chunkSize);

    if ($chunk < 0 || $chunk >= $numChunks) {
        echo json_encode([
            "length" => 0,
            "chunks" => $numChunks
        ]);
        exit;
    } else {
        $handle = fopen($filePath, 'rb');
        if ($handle === false) {
            http_response_code(500);
            echo json_encode(["error" => "Failed to open file"]);
            exit;
        }
        fseek($handle, $chunk * $chunkSize);
        $data = fread($handle, $chunkSize);
        $dataLength = strlen($data); // Yes, strlen() works for binary data in PHP.
        
        fclose($handle);

        echo json_encode([
            "data" => base64_encode($data),
            "chunk" => $chunk,
            "length" => $dataLength,
            "chunks" => $numChunks
        ]);
        exit;
    }
    exit;
}

http_response_code(400);
echo json_encode(["error" => "Unknown command"]);
