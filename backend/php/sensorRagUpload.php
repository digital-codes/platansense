<?php
declare(strict_types=1);

require 'vendor/autoload.php';

require_once __DIR__ . '/buildToken.php';
require_once __DIR__ . '/checkToken.php';
require_once __DIR__ . '/codec.php';
use function Adpcm\adpcm_decode;
use function Adpcm\adpcm_encode;

use Lcobucci\JWT\Encoding\JoseEncoder;
use Lcobucci\JWT\Token\Parser;
use Lcobucci\JWT\Signer\Key\InMemory;

header('Content-Type: application/json');

$keep_files = true; // Set to false to delete audio files after processing

// Load configuration
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

$audioDir = __DIR__ . "/audio/";
$dataDir = __DIR__ . "/data/";

// Ensure directories exist
if (!is_dir($audioDir)) {
    mkdir($audioDir, 0755, true);
}
if (!is_dir($dataDir)) {
    mkdir($dataDir, 0755, true);
}

// Load RAG data
$classifierPrompt = file_get_contents($dataDir . 'classifier_prompt.json');
$classesData = file_get_contents($dataDir . 'classes.json');
$promptsData = file_get_contents($dataDir . 'prompts.json');
$contextData = file_get_contents($dataDir . 'context.json');

if (!$classifierPrompt || !$classesData || !$promptsData || !$contextData) {
    http_response_code(500);
    echo json_encode(["error" => "RAG data files not found"]);
    exit;
}

$classifierPrompt = json_decode($classifierPrompt, true)['prompt'];
$classes = json_decode($classesData, true);
$prompts = json_decode($promptsData, true);
$contexts = json_decode($contextData, true);

// Configuration
$conversationTimeoutMinutes = 2; // Default timeout in minutes
$ollamaUrl = $config["SENSOR"]["chaturl"] ?? 'http://localhost:11434/v1/chat/completions';
$ollamaModel = $config["SENSOR"]["chatmodel"] ?? 'granite4.1:3b';

$whisper_cmd = $config["SENSOR"]["whisper_cmd"] ?? "whisper-cli";
$whisper_mdl = $config["SENSOR"]["whisper_mdl"] ?? "/opt/llama/whisper/models/ggml-base-q8_0.bin";

$piper_cmd = $config["SENSOR"]["piper_cmd"] ?? "/opt/pyenvs/pipertts/bin/piper";
$piper_mdl = $config["SENSOR"]["piper_mdl"] ?? "/opt/pyenvs/pipertts/voices/de_DE-thorsten-low.onnx";


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
    $identifiedBy = $id;
    if (!isset($devices[$id])) {
        http_response_code(401);
        echo json_encode(["status" => "not authorized0"]);
        exit;
    }
    $devKey = $devices[$id];
    $identifiedBy = "Sensor_" . $id;

    $challenge = bin2hex(openssl_random_pseudo_bytes(16));
    $iv = bin2hex(openssl_random_pseudo_bytes(16));
    $sessionId = bin2hex(random_bytes(8));

    file_put_contents("/tmp/challenge_{$id}_{$sessionId}.json", json_encode([
        "challenge" => $challenge,
        "iv" => $iv,
        "time" => time()
    ]));

    echo json_encode([
        "session" => $sessionId,
        "challenge" => $challenge,
        "iv" => $iv
    ]);

    exit;
}

// 2) CHALLENGE RESPONSE
if ($command === "challenge" && isset($input['id'], $input['session'], $input['challenge'])) {
    $id = $input['id'];
    $sessionId = $input['session'];

    $filePath = "/tmp/challenge_{$id}_{$sessionId}.json";
    if (!file_exists($filePath)) {
        http_response_code(401);
        echo json_encode(["status" => "not authorized2"]);
        exit;
    }
    $stored = json_decode(@file_get_contents($filePath), true);

    if (!$stored || time() - $stored['time'] > 60) {
        http_response_code(401);
        echo json_encode(["status" => "not authorized3"]);
        exit;
    }

    $devKey = $devices[$id];
    $keyBin = hex2bin($devKey);
    $ivBin = hex2bin($stored['iv']);
    $identifiedBy = "Sensor_" . $id;

    $expected = openssl_encrypt(
        hex2bin($stored['challenge']),
        "AES-128-CBC",
        $keyBin,
        OPENSSL_RAW_DATA | OPENSSL_ZERO_PADDING,
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

// raw data to wav for wav format
function pcmToWav(string $pcmData, int $sampleRate = 8000, int $bitsPerSample = 16): string
{
    $numChannels = 1;
    $byteRate = ($sampleRate * $numChannels * $bitsPerSample) / 8;
    $blockAlign = ($numChannels * $bitsPerSample) / 8;
    $subchunk2Size = strlen($pcmData);

    $header = '';
    $header .= pack('A4', 'RIFF');
    $header .= pack('V', 36 + $subchunk2Size);
    $header .= pack('A4', 'WAVE');
    $header .= pack('A4', 'fmt ');
    $header .= pack('V', 16);
    $header .= pack('v', 1);
    $header .= pack('v', $numChannels);
    $header .= pack('V', $sampleRate);
    $header .= pack('V', $byteRate);
    $header .= pack('v', $blockAlign);
    $header .= pack('v', $bitsPerSample);
    $header .= pack('A4', 'data');
    $header .= pack('V', $subchunk2Size);

    return $header . $pcmData;
}

// Helper function to query Ollama
function queryOllama($url, $model, $messages): array
{
    $payload = json_encode([
        "model" => $model,
        "messages" => $messages,
        "stream" => false
    ]);

    $ch = curl_init($url);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_POST, true);
    curl_setopt($ch, CURLOPT_HTTPHEADER, [
        "Content-Type: application/json"
    ]);
    curl_setopt($ch, CURLOPT_POSTFIELDS, $payload);
    curl_setopt($ch, CURLOPT_TIMEOUT, 60);

    error_log("Request to Ollama: " . json_encode($messages), 3, "llm.log");

    $response = curl_exec($ch);
    $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $error = curl_error($ch);
    curl_close($ch);

    error_log("Response status: $httpCode", 3, "llm.log");
    error_log("Response: $response", 3, "llm.log");

    if ($httpCode === 200 && $response) {
        $result = json_decode($response, true);
        $reply = $result['choices'][0]['message']['content'] ?? $result['message']['content'] ?? "";
        return [
            'status' => 'ok',
            'reply' => $reply
        ];
    } else {
        return [
            'status' => 'error',
            'reply' => "Error ($httpCode): $error"
        ];
    }
}

// Helper function to transcribe audio using Whisper
function transcribeAudio($audioFile): string
{
    $whisper_cmd = $config["SENSOR"]['whisper_cmd'] ?? 'whisper-cli';
    $whisper_mdl = $config["SENSOR"]['whisper_mdl'] ?? '/opt/llama/whisper/models/ggml-base-q8_0.bin';
    $outputFile = substr($audioFile, 0, -4) . '_txt';
    $cmd = sprintf(
        $whisper_cmd . ' -m ' . $whisper_mdl . ' -otxt -of %s -f %s -l de 2>&1',
        escapeshellarg($outputFile),
        escapeshellarg($audioFile)
    );

    exec($cmd, $output, $returnCode);

    if ($returnCode === 0 && file_exists($outputFile . '.txt')) {
        $text = trim(file_get_contents($outputFile . '.txt'));
        // error_log("Transcribed text: " . $text);
        global $keep_files;
        if (!$keep_files) {
            @unlink($outputFile . '.txt');
        }
        return $text;
    } else {
        error_log("Whisper transcription failed: " . implode("\n", $output));
    }

    return "";
}

// Helper function to synthesize speech using Piper
function synthesizeSpeech($text, $outputFile): bool
{
    global $piper_cmd, $piper_mdl, $keep_files;
    
    $tempTextFile = tempnam(sys_get_temp_dir(), 'piper_');
    file_put_contents($tempTextFile, $text);

    error_log("Synthesizing: " . $text . " to " . $outputFile, 3, "llm.log");
    error_log("Tempfile: " . $tempTextFile, 3, "llm.log");


    $outputDir = dirname($outputFile);
    if (!is_dir($outputDir)) {
        mkdir($outputDir, 0755, true);
    }

    // do not run this in background. returns only when finished
    $cmd = sprintf(
        $piper_cmd . ' -m ' . $piper_mdl . ' -i %s -f %s',
        escapeshellarg($tempTextFile),
        escapeshellarg($outputFile)
    );

    exec($cmd, $output, $returnCode);
    if (!$keep_files) {
        @unlink($tempTextFile);
    }

    return $returnCode === 0 && file_exists($outputFile);
}

// Helper function to play audio to bluetooth speaker
function playAudio($audioFile): bool
{
    $cmd = sprintf(
        'aplay -D bluealsa:DEV=20:0E:5A:1E:43:6C,PROFILE=a2dp,SRV=org.bluealsa %s 2>&1',
        escapeshellarg($audioFile)
    );

    exec($cmd, $output, $returnCode);

    return $returnCode === 0;
}

// Helper function to get conversation state
function getConversationState($sensorId, $dataDir): array
{
    $stateFile = $dataDir . $sensorId . '_conversation.json';
    if (file_exists($stateFile)) {
        $state = json_decode(file_get_contents($stateFile), true);
        if ($state && isset($state['messages'])) {
            return $state;
        }
    }
    return [
        'messages' => [],
        'last_interaction' => 0,
        'conversation_id' => null,
        'conversation_started' => 0,
        'message_count' => 0
    ];
}

// Helper function to clear conversation
function clearConversation($sensorId, $dataDir): void
{
    $stateFile = $dataDir . $sensorId . '_conversation.json';
    if (file_exists($stateFile)) {
        global $keep_files;
        if (!$keep_files) {
            @unlink($stateFile);
        }
    }
}

// Helper function to save conversation state
function saveConversationState($sensorId, $dataDir, $state): void
{
    $state['last_interaction'] = time();
    $stateFile = $dataDir . $sensorId . '_conversation.json';
    file_put_contents($stateFile, json_encode($state));
}

// Helper function to generate new conversation ID
function generateConversationId(): string
{
    return 'conv_' . bin2hex(random_bytes(8)) . '_' . time();
}

// Helper function to reset conversation state
function resetConversationState(): array
{
    return [
        'messages' => [],
        'last_interaction' => 0,
        'conversation_id' => generateConversationId(),
        'conversation_started' => time(),
        'message_count' => 0
    ];
}

// Helper function to classify user input
function classifyInput($text, $classifierPrompt, $ollamaUrl, $ollamaModel): array
{
    $messages = [
        ["role" => "system", "content" => $classifierPrompt],
        ["role" => "user", "content" => $text]
    ];

    $result = queryOllama($ollamaUrl, $ollamaModel, $messages);
    if ($result['status'] !== 'ok') {
        return ['categories' => [], 'error' => $result['reply']];
    }

    $categories = array_map('trim', explode(',', $result['reply']));
    return ['categories' => $categories, 'raw' => $result['reply']];
}

// 3) DATA PACKET
if ($command === "data" && isset($input['id']) && isset($input['token'], $input['data'])) {
    $token = $input['token'];
    $identifiedBy = "Sensor_" . $input['id'];
    
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
    
    $sensorId = $parsedToken->claims()->get('sensor');
    $uuid = uniqid($identifiedBy . "_", true);
    
    try {
        // Decode and process audio
        $audioFormat = $input['format'] ?? 'adpcm';
        $audioData = base64_decode($input['data'], true);
        
        if ($audioData === false) {
            http_response_code(400);
            echo json_encode(["status" => "data invalid"]);
            exit;
        }
        
        if (strlen($audioData) > 512 * 1024) {
            http_response_code(401);
            echo json_encode(["status" => "data too large"]);
            exit;
        }
        
        // Convert from ADPCM if needed
        if ($audioFormat == "adpcm") {
            $audioData = adpcm_decode($audioData);
            if (is_array($audioData)) {
                $pcm = '';
                foreach ($audioData as $sample) {
                    $val = (int)$sample;
                    if ($val < -32768) $val = -32768;
                    elseif ($val > 32767) $val = 32767;
                    $pcm .= pack('v', $val & 0xFFFF);
                }
                $audioData = $pcm;
            }
        }
        
        // Add WAV header and save
        $audioData = pcmToWav($audioData, 8000, 16);
        $audioFile = $audioDir . $uuid . ".wav";
        
        if (file_put_contents($audioFile, $audioData) === false) {
            http_response_code(500);
            echo json_encode(["error" => "Failed to write audio file"]);
            exit;
        }
        
        // Transcribe audio to text using Whisper
        $transcribedText = transcribeAudio($audioFile);
        
        if (empty($transcribedText)) {
            clearConversation($sensorId, $dataDir);
            echo json_encode(["uuid" => $uuid, "status" => "transcription_failed"]);
            exit;
        }
        
        // Check for stop command or conversation timeout
        $conversationState = getConversationState($sensorId, $dataDir);
        $shouldClearConversation = false;
        $conversationReset = false;
        $previousConversationId = $conversationState['conversation_id'] ?? null;
        
        // Clear if text starts with "stop"
        if (stripos(trim($transcribedText), 'stop') === 0) {
            $shouldClearConversation = true;
        }
        
        // Clear if previous input is too old
        if (!empty($conversationState['messages']) && $conversationState['last_interaction'] > 0) {
            $timeDiff = (time() - $conversationState['last_interaction']) / 60;
            if ($timeDiff > $conversationTimeoutMinutes) {
                $shouldClearConversation = true;
            }
        }
        
        if ($shouldClearConversation) {
            clearConversation($sensorId, $dataDir);
            $conversationState = resetConversationState();
            $conversationReset = true;
        } elseif (empty($conversationState['conversation_id'])) {
            // Initialize conversation if it doesn't have an ID
            $conversationState = resetConversationState();
            $conversationReset = true;
        }
        
        // Track current conversation ID
        $currentConversationId = $conversationState['conversation_id'];
        
        // Classify the input to determine context
        $classification = classifyInput($transcribedText, $classifierPrompt, $ollamaUrl, $ollamaModel);
        
        // Build context based on classification
        $contextText = "";
        foreach ($classification['categories'] as $category) {
            if (isset($contexts[$category])) {
                foreach ($contexts[$category] as $ctx) {
                    if (isset($ctx[$category])) {
                        $contextText .= $ctx[$category] . "\n\n";
                    }
                }
            }
        }
        
        // Select appropriate prompt based on classification
        $selectedPrompt = $prompts['Alchimist'] ?? $prompts['default'] ?? "Du bist ein hilfreicher Assistent.";
        
        // Prepare messages for LLM
        $messages = [
            ["role" => "system", "content" => $selectedPrompt]
        ];
        
        // Add context if available
        if (!empty($contextText)) {
            $messages[] = ["role" => "system", "content" => "Kontextinformationen:\n" . $contextText];
        }
        
        // Add conversation history
        foreach ($conversationState['messages'] as $msg) {
            $messages[] = ["role" => $msg['role'], "content" => $msg['content']];
        }
        
        // Add current user input
        $messages[] = ["role" => "user", "content" => $transcribedText];
        
        // Query LLM for response
        $llmResponse = queryOllama($ollamaUrl, $ollamaModel, $messages);
        
        if ($llmResponse['status'] !== 'ok') {
            echo json_encode(["uuid" => $uuid, "status" => "llm_failed", "error" => $llmResponse['reply']]);
            exit;
        }
        
        $responseText = trim($llmResponse['reply']);
        
        // Update conversation state
        $conversationState['messages'][] = ["role" => "user", "content" => $transcribedText];
        $conversationState['messages'][] = ["role" => "assistant", "content" => $responseText];
        $conversationState['message_count'] = count($conversationState['messages']) / 2; // Count message pairs
        
        // Limit conversation history to last 10 messages
        if (count($conversationState['messages']) > 10) {
            $conversationState['messages'] = array_slice($conversationState['messages'], -10);
        }
        
        saveConversationState($sensorId, $dataDir, $conversationState);
        
        // Synthesize response to audio using Piper
        $responseAudioFile = $audioDir . $uuid . "_response.wav";
        $synthesised = synthesizeSpeech($responseText, $responseAudioFile);
        
        if (!$synthesised) {
            echo json_encode(["uuid" => $uuid, "status" => "tts_failed"]);
            exit;
        }
        
        // Play response audio to bluetooth speaker
        $played = playAudio($responseAudioFile);
        
        // Clean up temporary audio files
        global $keep_files;
        if (!$keep_files) {
            @unlink($audioFile);
            @unlink($responseAudioFile);
        }
        
        // Send response
        echo json_encode([
            "uuid" => $uuid,
            "status" => "ok",
            "transcription" => $transcribedText,
            "classification" => $classification['categories'],
            "response" => $responseText,
            "audio_played" => $played,
            "conversation_id" => $currentConversationId,
            "conversation_reset" => $conversationReset,
            "conversation_timestamp" => $conversationState['conversation_started'],
            "message_count" => $conversationState['message_count']
        ]);
        
    } catch (Exception $e) {
        http_response_code(500);
        echo json_encode(["error" => "Processing failed: " . $e->getMessage()]);
        exit;
    }
    
    exit;
}

http_response_code(400);
echo json_encode(["error" => "Unknown command"]);