<?php
declare(strict_types=1);

use Lcobucci\JWT\Encoding\JoseEncoder;
use Lcobucci\JWT\Token\Parser;
use Lcobucci\JWT\Validation\Constraint\RelatedTo;
use Lcobucci\JWT\Validation\Constraint\IssuedBy;
use Lcobucci\JWT\Validation\Constraint\IdentifiedBy;
use Lcobucci\JWT\Validation\Constraint\SignedWith;
use Lcobucci\JWT\Validation\Constraint\StrictValidAt;
use Lcobucci\JWT\Validation\Validator;
use Lcobucci\Clock\SystemClock;
use Lcobucci\JWT\Signer\Hmac\Sha256;


require 'vendor/autoload.php';

/* 
$parser = new Parser(new JoseEncoder());

$token = $parser->parse(
    'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.'
    . 'eyJzdWIiOiIxMjM0NTY3ODkwIn0.'
    . '2gSBz9EOsQRN9I-3iSxJoFt7NtgV6Rm0IL6a8CAwl3Q'
);

$validator = new Validator();

if (! $validator->validate($token, new RelatedTo('1234567891'))) {
    echo 'Invalid token (1)!', PHP_EOL; // will print this
}

if (! $validator->validate($token, new RelatedTo('1234567890'))) {
    echo 'Invalid token (2)!', PHP_EOL; // will not print this
}

// Example usage:
/*
$token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.'
    . 'eyJzdWIiOiIxMjM0NTY3ODkwIn0.'
    . '2gSBz9EOsQRN9I-3iSxJoFt7NtgV6Rm0IL6a8CAwl3Q'
;

if (!validateToken($token, '1234567890', 'issuer_example', 'jti_example')) {
    echo 'Token failed custom validation!', PHP_EOL;
}

*/

function validateToken($tokenString, $relatedTo, $issuedBy, $identifiedBy, $signingKey = null): bool {
    $parser = new Parser(new JoseEncoder());
    $token = $parser->parse($tokenString);
    $validator = new Validator();
    if (! $validator->validate($token, new IdentifiedBy($identifiedBy))) {
        // echo 'Invalid token (1)!', PHP_EOL; // will print this
        return false;
    }
    if (! $validator->validate($token, new RelatedTo($relatedTo))) {
        // echo 'Invalid token (2)!', PHP_EOL; // will not print this
        return false;
    }
    if (! $validator->validate($token, new IssuedBy($issuedBy))) {
        // echo 'Invalid token (3)!', PHP_EOL; // will not print this
        return false;
    }
    // Validate the token's signature if key is provided
    if ($signingKey === null) {
        // echo 'No signing key provided, skipping signature validation!', PHP_EOL;
    } else {
        if (! $validator->validate($token, new SignedWith(new Sha256(), $signingKey))) {
            // echo 'Invalid token signature!', PHP_EOL;
            return false;
        }
    }
    // Validate the token's validity period
    // Create a clock in UTC
    $clock = SystemClock::fromUTC(); // Adjusted to UTC with a 1-hour offset
    $leeway = new DateInterval('PT10S'); // 10 seconds leeway
    if (! $validator->validate($token, new StrictValidAt($clock, $leeway))) {
        // echo 'Token is not valid at this time!', PHP_EOL;
        return false;
    }
    return true;
}

