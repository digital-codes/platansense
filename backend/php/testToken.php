<?php
declare(strict_types=1);

require_once __DIR__ . '/buildToken.php';
require_once __DIR__ . '/checkToken.php';

use Lcobucci\JWT\Encoding\JoseEncoder;
use Lcobucci\JWT\Token\Parser;
use Lcobucci\JWT\Signer\Key\InMemory;
require 'vendor/autoload.php';

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

$identifiedBy = '1';

$token = createToken($key, $identifiedBy, $relatedTo, $issuedBy);
echo 'Created Token: ', $token, PHP_EOL;

if (!validateToken($token, $relatedTo, $issuedBy, $identifiedBy, $key)) {
    echo 'Token failed custom validation!', PHP_EOL;
} else {
    echo 'Token is valid!', PHP_EOL;
    $parser = new Parser(new JoseEncoder());
    try {
        $parsedToken = $parser->parse($token);
    } catch (Exception $e) {
        echo 'Error parsing token: ', $e->getMessage(), PHP_EOL;
        return;
    }
    $id = $parsedToken->claims()->get('sensor');
    if (isset($id)) {
        echo 'sensor: ', $id, PHP_EOL;
    } else {
        echo 'sensor not found in token.', PHP_EOL;
    }
}
echo 'Token: ', $token, PHP_EOL;    

