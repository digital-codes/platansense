<?php

/*Example cURL request to send an audio file for transcription and analysis using Mistral AI's API. Replace `<audio_base64>` with the base64-encoded audio content and set your `MISTRAL_API_KEY` environment variable before running the command.
*/
/*
curl --location https://api.mistral.ai/v1/chat/completions \
  --header "Authorization: Bearer $MISTRAL_API_KEY" \
  --header "Content-Type: application/json" \
  --data '{
    "model": "voxtral-mini-latest",
    "messages": [
      {
        "role": "user",
        "content": [
          {
            "type": "input_audio",
            "input_audio": "<audio_base64>",
          },
          {
            "type": "text",
            "text": "What'\''s in this file?"
          }
        ]
      }
    ]
  }'
*/

/* example queryy to tts service 
curl -X POST https://api.murf.ai/v1/speech/stream \
     -H "api-key: xxxx" \
     -H "Content-Type: application/json" \
     -d '{
  "text": "Hallo Platane wie gehts? wie ist das Wetter heute?",
  "voice_id":"Josephine",
  "style":"Conversational",
  "sampleRate": 8000,
  "channelType": "MONO",
  "format": "WAV",
  "pitch": 0,
  "model": "FALCON",
  "multiNativeLocale": "de-DE"
}' --output tts.wav



*/

// $key   = InMemory::plainText(random_bytes(32));
$config = parse_ini_file('/var/www/files/platane/config.ini', true);
if (!$config || !isset($config['SENSOR']['chaturl']) || !isset($config['SENSOR']['chatkey']) 
    || !isset($config['SENSOR']['ttsurl']) || !isset($config['SENSOR']['ttskey']) 
    || !isset($config['SENSOR']['ttsvoices']) || !isset($config['SENSOR']['chatmodel']) ) {
    http_response_code(500);
    echo json_encode(["error" => "Config invalid"]);
    exit;
}

$audioDir = __DIR__ . "/audio/";
// ensure audio directory exists
if (!is_dir($audioDir)) {
    mkdir($audioDir, 0755, true);
}



function chatQuery($key, $model, $url, $messages): array
{

    // Prepare request payload
    $payload = json_encode([
        "model" => $model,
        "messages" => $messages,
        "temperature" => 0.1, // Example temperature setting
    ]);

    // Set up cURL
    $ch = curl_init($url);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_POST, true);
    curl_setopt($ch, CURLOPT_HTTPHEADER, [
        "Content-Type: application/json",
        "Authorization: Bearer $key"
    ]);
    curl_setopt($ch, CURLOPT_POSTFIELDS, $payload);

    // Execute and get the response
    $response = curl_exec($ch);
    $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);

    // Handle the response
    if ($httpCode === 200) {
        $result = json_decode($response, true);
        $reply = $result['choices'][0]['message']['content'] ?? "No reply.";
        $result = [
            'status' => 'ok',
            'reply' => $reply
        ];
    } else {
        $result = [
            'status' => 'error',
            'reply' => "Error ($httpCode): $response"
        ];
    }
    return $result;
}

function ttsQuery($key, $url, $text, $voice): array
{
    // Prepare request payload
    $payload = json_encode([
        "text" => $text,
        "voice_id" => $voice,
        "style" => "Conversational",
        "sampleRate" => 8000,
        "channelType" => "MONO",
        "format" => "WAV",
        "pitch" => 0,
        "model" => "FALCON",
        "multiNativeLocale" => "de-DE"
    ]);

    // Set up cURL
    $ch = curl_init($url);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_POST, true);
    curl_setopt($ch, CURLOPT_HTTPHEADER, [
        "Content-Type: application/json",
        "api-key: $key"
    ]);
    curl_setopt($ch, CURLOPT_POSTFIELDS, $payload);

    // Execute and get the response
    $response = curl_exec($ch);
    $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);

    // Handle the response
    if ($httpCode === 200) {
        $result = [
            'status' => 'ok',
            'audio_data' => $response
        ];
    } else {
        $result = [
            'status' => 'error',
            'reply' => "Error ($httpCode): $response"
        ];
    }
    return $result;
}


$messages = [
    ["role" => "system", "content" => "Du bist eine Platane in Karlsruhe. Erfinde eine Antwort basierend auf dem Audio. 
    Berücksichte dabei schlechte Qualität der Audiodaten und versuche das Gesprochene bestmöglich zu transkribieren.
    Beachte, dass du häufig als Baum angesprochen wirst, z.B. als Platane oder als Banane. Unterscheide dies.
    Antworte in Deutsch im JSON Format mit den Feldern Transscript und Antwort.
    Wenn die Audiodaten unverständlich sind, gib ein leeres Transscript Feld zurück und der Antwort: 
    das habe ich nicht verstanden.
    Verwende nur dieses Format und nichts anderes."],
    ["role" => "user", "content" => [
        [
            "type" => "input_audio",
            "input_audio" => base64_encode(file_get_contents('./audio/sensor.wav')),
        ]
    ]]
];

$name = "sensor";

$result = chatQuery(
    $config['SENSOR']['chatkey'],
    $config['SENSOR']['chatmodel'],
    $config['SENSOR']['chaturl'],
    $messages
);
print_r($result);

if (!empty($result['reply']) && is_string($result['reply'])) {
    $replyText = $result['reply'];

    // extract JSON inside a fenced code block (```json ... ``` or ```)
    if (preg_match('/```(?:json)?\s*(.*?)\s*```/is', $replyText, $m)) {
        $jsonText = $m[1];
    } else {
        $jsonText = $replyText;
    }

    // clean and decode
    $jsonText = trim($jsonText, " \t\n\r\0\x0B`");
    $decoded = json_decode($jsonText, true);

    if (json_last_error() === JSON_ERROR_NONE) {
        $result['reply'] = $decoded;
    } else {
        // keep original reply and add error info for debugging
        $result['reply_parse_error'] = json_last_error_msg();
    }
}

print_r($result);


// prepare json file path
$jsonFile = $audioDir . $name . '.json';

// encode result to JSON
$jsonData = json_encode($result, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE);

if ($jsonData === false) {
    $err = json_last_error_msg();
    echo "Failed to encode result to JSON: $err" . PHP_EOL;
} else {
    $written = file_put_contents($jsonFile, $jsonData);
    if ($written === false) {
        echo "Failed to write JSON to file: $jsonFile" . PHP_EOL;
    } else {
        echo "Result saved to $jsonFile" . PHP_EOL;
    }
}


if (isset($result['reply']['Antwort'])) {
    $ttsResult = ttsQuery(
        $config['SENSOR']['ttskey'],
        $config['SENSOR']['ttsurl'],
        $result['reply']['Antwort'],
        explode(',', $config['SENSOR']['ttsvoices'])[0]
    );
    if ($ttsResult['status'] === 'ok') {
        file_put_contents($audioDir . $name . '_chat.wav', $ttsResult['audio_data']);
        echo ("TTS audio saved to " . $audioDir . $name . "_chat.wav" . PHP_EOL);
    } else {
        echo ("TTS Error: " . $ttsResult['reply'] . PHP_EOL);
    }
} else {
    echo ("No Antwort field in reply." . PHP_EOL);
}   

echo ("OK" . PHP_EOL);
?>
