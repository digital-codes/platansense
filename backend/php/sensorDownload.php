<?php
declare(strict_types=1);

require_once __DIR__ . '/buildToken.php';
require_once __DIR__ . '/checkToken.php';


header('Content-Type: application/json');

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
if ($command === "check" && isset($input['name'])) {
    $name = $input['name'];

    $filePath = $audioDir . $name . ".adpcm";
    if (!file_exists($filePath)) {
        http_response_code(404);
        echo json_encode(["status" => "file not found"]);
        exit;
    }

    $fileSize = filesize($filePath);
    $numChunks = (int)ceil($fileSize / $chunkSize);

    echo json_encode([
        "chunks" => $numChunks
    ]);

    exit;
}

// 2) DOWN RESPONSE
if ($command === "down" && isset($input['name']) && isset($input['chunk'])) {
    $name = $input['name'];
    $chunk = (int)$input['chunk'];

    $filePath = $audioDir . $name . ".adpcm";
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
