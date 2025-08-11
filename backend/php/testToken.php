<?php
declare(strict_types=1);

require_once __DIR__ . '/buildToken.php';
require_once __DIR__ . '/checkToken.php';

use Lcobucci\JWT\Encoding\JoseEncoder;
use Lcobucci\JWT\Token\Parser;
use Lcobucci\JWT\Signer\Key\InMemory;
require 'vendor/autoload.php';


$identifiedBy = 'sensor1';
$relatedTo = 'component1';
$issuedBy = 'http://example.com';

$key   = InMemory::plainText(b"secretSensorkeyForJwTTestingAndO");

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

