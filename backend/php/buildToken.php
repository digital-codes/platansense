<?php
declare(strict_types=1);

use Lcobucci\JWT\Encoding\ChainedFormatter;
use Lcobucci\JWT\Encoding\JoseEncoder;
use Lcobucci\JWT\Signer\Hmac\Sha256;
use Lcobucci\JWT\Token\Builder;

require 'vendor/autoload.php';



/*
$tokenBuilder = (new Builder(new JoseEncoder(), ChainedFormatter::default()));
$algorithm    = new Sha256();
$signingKey   = InMemory::plainText(random_bytes(32));

$now   = new DateTimeImmutable();
$token = $tokenBuilder
    // Configures the issuer (iss claim)
    ->issuedBy('http://example.com')
    // Configures the audience (aud claim)
    ->permittedFor('http://example.org')
    // Configures the subject of the token (sub claim)
    ->relatedTo('component1')
    // Configures the id (jti claim)
    ->identifiedBy('4f1g23a12aa')
    // Configures the time that the token was issue (iat claim)
    ->issuedAt($now)
    // Configures the time that the token can be used (nbf claim)
    ->canOnlyBeUsedAfter($now->modify('+1 second'))
    // Configures the expiration time of the token (exp claim)
    ->expiresAt($now->modify('+10 minute'))
    // Configures a new claim, called "uid"
    ->withClaim('uid', 1)
    // Configures a new header, called "foo"
    ->withHeader('foo', 'bar')
    // Builds a new token
    ->getToken($algorithm, $signingKey);

    */



function createToken($signingKey, string $sensorId, string $relatedTo, string $issuedBy): string {
    $tokenBuilder = (new Builder(new JoseEncoder(), ChainedFormatter::default()));
    $algorithm    = new Sha256();

    $now   = new DateTimeImmutable();
    $token = $tokenBuilder
        ->issuedBy($issuedBy)
        // ->permittedFor('http://example.org')
        ->relatedTo($relatedTo)
        ->identifiedBy($sensorId)
        ->issuedAt($now)
        ->canOnlyBeUsedAfter($now->modify('+1 second'))
        ->expiresAt($now->modify('+10 minute'))
        ->withClaim('model', "any")
        ->withClaim('sensor', $sensorId)
        //->withHeader('foo', 'bar')
        ->getToken($algorithm, $signingKey);

    return $token->toString();
}

/*
$token = createToken('4f1g23a12aa', 'component1', 'http://example.com');
echo $token;    
*/