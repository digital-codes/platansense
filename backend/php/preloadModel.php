<?php

$config = parse_ini_file('/var/www/files/platane/config.ini', true);

if (
    $config === false ||
    !isset($config['SENSOR']['chatmodel'])
) {
    die("Unable to read chatmodel from config.\n");
}

$model = $config['SENSOR']['chatmodel'];

$ch = curl_init('http://127.0.0.1:11434/api/generate');

curl_setopt_array($ch, [
    CURLOPT_POST => true,
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_HTTPHEADER => [
        'Content-Type: application/json',
    ],
    CURLOPT_POSTFIELDS => json_encode([
        'model'      => $model,
        'prompt'     => '',
        'stream'     => false,
        'keep_alive' => -1,
    ]),
]);

$response = curl_exec($ch);

if ($response === false) {
    die('cURL error: ' . curl_error($ch) . PHP_EOL);
}

$httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
curl_close($ch);

if ($httpCode !== 200) {
    die("HTTP $httpCode\n$response\n");
}

echo "Model '$model' loaded and pinned in memory.\n";

