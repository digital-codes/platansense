<?php
declare(strict_types=1);

require_once __DIR__ . '/buildToken.php';
require_once __DIR__ . '/checkToken.php';

use Lcobucci\JWT\Encoding\JoseEncoder;
use Lcobucci\JWT\Token\Parser;
use Lcobucci\JWT\Signer\Key\InMemory;
require 'vendor/autoload.php';

// $key   = InMemory::plainText(random_bytes(32));
$key = InMemory::plainText(b"secretSensorkeyForJwTTestingAndO");

$devKey = "00112233445566778899aabbccddeeff";

$identifiedBy = 'sensor1';
$relatedTo = 'component1';
$issuedBy = 'http://example.com';



header('Content-Type: application/json');


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
    if ($id != $identifiedBy) {
        http_response_code(401);
        echo json_encode(["status" => "not authorized1"]);
        exit;
    }

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
    if ($id != $identifiedBy) {
        http_response_code(401);
        echo json_encode(["status" => "not authorized2"]);
        exit;
    }

    $sessionId = $input['session'];

    $filePath = "/tmp/challenge_{$id}_{$sessionId}.json";
    $stored = json_decode(@file_get_contents($filePath), true);

    // Same expiry check
    if (!$stored || time() - $stored['time'] > 60) {
        http_response_code(401);
        echo json_encode(["status" => "not authorized3"]);
        exit;
    }

    $keyBin = hex2bin($devKey);
    $ivBin = hex2bin($stored['iv']);

    $expected = openssl_encrypt(
        hex2bin($stored['challenge']),
        "AES-256-CBC",  // was 128
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
if ($command === "data" && isset($input['token'], $input['data'])) {
    $token = $input['token'];
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

    $uuid = uniqid($id . "_", true);
    try {
        file_put_contents("/tmp/data_$uuid.json", json_encode([
            "device" => $id,
            "data" => $input['data'],
            "time" => time()
        ]));
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
