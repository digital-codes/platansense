<?php
// sensorChat.php
// Usage: php sensorChat.php /path/to/dir 5
$audioDir = __DIR__ . "/audio/";
$interval = max(3, (int)($argv[2] ?? 5));

if (!is_dir($audioDir)) {
    fwrite(STDERR, "Directory not found: $audioDir\n");
    exit(1);
}

// support graceful shutdown if pcntl is available
$running = true;
if (function_exists('pcntl_async_signals')) {
    pcntl_async_signals(true);
    pcntl_signal(SIGINT, function() use (&$running){ $running = false; });
    pcntl_signal(SIGTERM, function() use (&$running){ $running = false; });
}

$dir = rtrim($audioDir, DIRECTORY_SEPARATOR);

while ($running) {
    foreach (glob($audioDir . DIRECTORY_SEPARATOR . 'Sensor*.lock') as $lockPath) {
        $base = pathinfo($lockPath, PATHINFO_FILENAME); // e.g. Sensor123

        $wavPath = $audioDir . DIRECTORY_SEPARATOR . $base . '_chat.wav';
        if (!file_exists($wavPath)) {
            $scriptPath = __DIR__ . '/sensorChatLlm.php'; // adjust filename as needed
            $cmd = escapeshellarg(PHP_BINARY) . ' ' . escapeshellarg($scriptPath) . ' ' . escapeshellarg($base);
            $chatResponse = @shell_exec($cmd);
            if ($chatResponse === null) {
                fwrite(STDERR, date('c') . " Failed to execute script: $scriptPath $base\n");
                $chatResponse = '';
            }
        }
    }

    sleep($interval);
}

exit(0);
?>