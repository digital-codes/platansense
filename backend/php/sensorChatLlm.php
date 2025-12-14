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
if (
    !$config || !isset($config['SENSOR']['chaturl']) || !isset($config['SENSOR']['chatkey'])
    || !isset($config['SENSOR']['ttsurl']) || !isset($config['SENSOR']['ttskey'])
    || !isset($config['SENSOR']['ttsvoices']) || !isset($config['SENSOR']['chatmodel'])
) {
    http_response_code(500);
    echo json_encode(["error" => "Config invalid"]);
    exit;
}

$audioDir = __DIR__ . "/audio/";
// ensure audio directory exists
if (!is_dir($audioDir)) {
    mkdir($audioDir, 0755, true);
}



function chatQuery($key, $model, $url, $name): array
{
    global $audioDir;
    $audioPath = $audioDir . $name . '.wav';
    $audioBase64 = '';
    if (!file_exists($audioPath)) {
        return ["status" => "error", "reply" => "Audio file not found: $audioPath"];
    }
    $audioData = file_get_contents($audioPath);
    if ($audioData === false) {
        return ["status" => "error", "reply" => "Failed to read audio file: $audioPath"];
    }
    $audioBase64 = base64_encode($audioData);

    $messages = [
        [
            "role" => "system",
            "content" => "Du bist eine Platane in Karlsruhe. Erfinde eine Antwort basierend auf den Audiodaten. 
            Berücksichte dabei schlechte Qualität der Audiodaten und versuche das Gesprochene bestmöglich zu transkribieren.
            Beachte, dass du häufig als Baum angesprochen wirst, z.B. als Platane oder als Banane. Unterscheide dies.
            Interpretiere die Eingabe grosszügig aber möglichst korrekt. Argumentiere nicht zu streng.
            Antworte in Deutsch im JSON Format mit den Feldern Transscript und Antwort.
            Wenn die Audiodaten unverständlich sind, gib ein leeres Transscript Feld zurück und der Antwort: 
            das habe ich nicht verstanden.
            Verwende nur dieses Format und nichts anderes."
        ],
    ];

    $messages[] = [
        "role" => "user",
        "content" => [
            [
                "type" => "input_audio",
                "input_audio" => $audioBase64,
            ],
        ]
    ];


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
            "model" => $model,
            "prompt" => (isset($messages[0]) && isset($messages[0]['role']) && $messages[0]['role'] === 'system') ? [$messages[0]['content']] : [],
            "url" => $url,
            'reply' => $reply
        ];
    } else {
        $result = [
            'status' => 'error',
            "model" => $model,
            "url" => $url,
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
            "url" => $url,
            'audio_data' => $response
        ];
    } else {
        $result = [
            'status' => 'error',
            "url" => $url,
            'reply' => "Error ($httpCode): $response"
        ];
    }
    return $result;
}

function localTts($text, $name): array
{
    $postFields = [
        'text' => $text,
        'file' => $name
    ];
    // synthesizer 
    $port = 9010;
    $host = 'localhost';
    $ttsUrl = "http://$host:$port/transscribe"; // or any endpoint you defined
    // Prepare cURL for POST
    $ch = curl_init($ttsUrl);
    curl_setopt($ch, CURLOPT_POST, true);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_HTTPHEADER, ['Content-Type: application/json']);
    curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($postFields));

    // Execute POST request
    $ttsResponse = curl_exec($ch);
    $ttsHttpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $ttsError = curl_error($ch);
    curl_close($ch);

    if ($ttsHttpCode !== 200 || !$ttsResponse) {
        return [
            'status' => 'error',
            'url' => $ttsUrl,
            'reply' => "TTS failed: $ttsHttpCode"
        ];
    }
    // Try to extract filename from TTS response if present (assume JSON with 'filename')
    $ttsJson = json_decode($ttsResponse, true);
    if (is_array($ttsJson) && isset($ttsJson['filename'])) {
        $audioFile = $ttsJson['filename'];
    } else {
        return [
            'status' => 'error',
            'url' => $ttsUrl,
            'reply' => "TTS did not return filename"
        ];
    }

    return [
        'status' => 'ok',
        'url' => $ttsUrl,
        'audio_file' => $audioFile
    ];

}


function ttsQueryEl($key, $url, $text, $voice): array
{
    /*
    curl -X POST "https://api.elevenlabs.io/v1/text-to-speech/<voice>?output_format=pcm_8000" \
  -H "xi-api-key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hallo, ich bin Helmut. Wie kann ich Ihnen helfen?",
    "model_id": "eleven_multilingual_v2"
  }' \
    --output output.wav

    */
    // ElevenLabs TTS: voice is appended to the base URL and output format is a URL parameter.
    // Returns binary WAV in 'audio_data' on success.
    $endpoint = rtrim($url, '/') . '/' . rawurlencode($voice) . '?output_format=pcm_8000';

    $payload = json_encode([
        "text" => $text,
        "model_id" => "eleven_multilingual_v2"
    ]);

    $ch = curl_init($endpoint);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_POST, true);
    curl_setopt($ch, CURLOPT_HTTPHEADER, [
        "Content-Type: application/json",
        "xi-api-key: $key"
    ]);
    curl_setopt($ch, CURLOPT_POSTFIELDS, $payload);

    // execute
    $response = curl_exec($ch);
    $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $curlErr = null;
    if ($response === false) {
        $curlErr = curl_error($ch);
    }
    curl_close($ch);

    if ($response === false) {
        return [
            'status' => 'error',
            'url' => $endpoint,
            'reply' => "cURL error: $curlErr"
        ];
    }

    if ($httpCode === 200) {
        $pcm = $response;
        $sampleRate = 8000;
        $bitsPerSample = 16;
        $channels = 1;
        $byteRate = (int) ($sampleRate * $channels * ($bitsPerSample / 8));
        $blockAlign = (int) ($channels * ($bitsPerSample / 8));
        $dataSize = strlen($pcm);

        // WAV header (RIFF little-endian)
        $header = "RIFF" . pack('V', 36 + $dataSize) .
            "WAVE" .
            "fmt " . pack('V', 16) . // Subchunk1Size for PCM
            pack('v', 1) .           // AudioFormat PCM = 1
            pack('v', $channels) .
            pack('V', $sampleRate) .
            pack('V', $byteRate) .
            pack('v', $blockAlign) .
            pack('v', $bitsPerSample) .
            "data" . pack('V', $dataSize);

        $response = $header . $pcm;
        return [
            'status' => 'ok',
            'url' => $endpoint,
            'audio_data' => $response
        ];
    }

    return [
        'status' => 'error',
        'url' => $endpoint,
        'reply' => "Error ($httpCode): " . $response
    ];

}

function handleQuery($name, $tts = "murf", $voicenum = 1)
{
    global $config, $audioDir;
    $llmResponse = chatQuery(
        $config['SENSOR']['chatkey'],
        $config['SENSOR']['chatmodel'],
        $config['SENSOR']['chaturl'],
        $name
    );
    // check response status
    if ($llmResponse['status'] !== 'ok') {
        return $llmResponse;
    }

    // decode JSON reply
    if (!empty($llmResponse['reply']) && is_string($llmResponse['reply'])) {
        $replyText = $llmResponse['reply'];

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
            $llmResponse['reply'] = $decoded;
        } else {
            $llmResponse["status"] = "error";
            $llmResponse["reply"] = "Failed to parse JSON from LLM reply.";
            return $llmResponse;
        }

        // write json file
        // prepare json file path
        $jsonFile = $audioDir . $name . '.json';

        // encode result to JSON
        $jsonData = json_encode($llmResponse, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE);

        if ($jsonData === false) {
            $err = json_last_error_msg();
            $llmResponse["status"] = "error";
            $llmResponse["reply"] = "Failed to encode result to JSON: $err";
            return $llmResponse;
        } else {
            $written = file_put_contents($jsonFile, $jsonData);
            if ($written === false) {
                $llmResponse["status"] = "error";
                $llmResponse["reply"] = "Failed to write JSON to file: $jsonFile";
                return $llmResponse;
            }
        }

        // synthesize answer if Transscript and Antwort are present
        if (isset($llmResponse['reply']['Antwort'])) {
            if ($tts == "murf") {
                $ttsResult = ttsQuery(
                    $config['SENSOR']['ttskey'],
                    $config['SENSOR']['ttsurl'],
                    $llmResponse['reply']['Antwort'],
                    explode(',', $config['SENSOR']['ttsvoices'])[$voicenum]
                );
            }
            if ($tts == "eleven") {
                $ttsResult = ttsQueryEl(
                    $config['SENSOR']['ttskey_el'],
                    $config['SENSOR']['ttsurl_el'],
                    $llmResponse['reply']['Antwort'],
                    explode(',', $config['SENSOR']['ttsvoices_el'])[$voicenum]
                );
            }
            if ($tts == "local") {
                $ttsResult = localTts(
                    $llmResponse['reply']['Antwort'],
                    $audioDir . $name . '_chat.wav'
                );
            }
            //  check tts result
            if (!$ttsResult) {
                $llmResponse["status"] = "error";
                $llmResponse["reply"] = "TTS query failed.";
                return $llmResponse;
            }
            // 
            if ($ttsResult['status'] === 'ok') {
                // local returns the wav file already
                if ($tts != "local") {
                    file_put_contents($audioDir . $name . '_chat.wav', $ttsResult['audio_data']);
                }
                $llmResponse['tts_audio_file'] = $audioDir . $name . '_chat.wav';
            } else {
                $llmResponse["status"] = "error";
                $llmResponse["reply"] = "TTS Error: " . $ttsResult['reply'];
                return $llmResponse;
            }
        } else {
            $llmResponse["status"] = "error";
            $llmResponse["reply"] = "No Antwort field in reply.";
            return $llmResponse;
        }
    }
    // done
    return $llmResponse;
}

// get name from CLI (or from GET as fallback), call handleQuery and output JSON
global $argv;
if (!isset($argv[1]) || trim($argv[1]) === '') {
    fwrite(STDERR, "Usage: php " . basename(__FILE__) . " <name>\n");
    exit(1);
}
$name = trim($argv[1]);

$result = handleQuery($name, "local", 1);

//print_r($result);

return $result;

