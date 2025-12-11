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
        // check .adpcm first, then check for .wav  
        $adpcmPath = $audioDir . DIRECTORY_SEPARATOR . $base . '_chat.adpcm';

        if (!file_exists($adpcmPath)) {
            // try to create atomically; if another process creates it concurrently, fopen('x') will fail
            $fp = @fopen($adpcmPath, 'x');
            if ($fp !== false) {
                try {
                    fwrite($fp, "1234567890");
                    fflush($fp);
                } catch (Throwable $e) {
                    echo date('c') . " Error writing to: $adpcmPath - " . $e->getMessage() . "\n";  
                }
                fclose($fp);
                echo date('c') . " Created: $adpcmPath\n";
            } else {
                // ignore if already exists, otherwise report
                if (!file_exists($adpcmPath)) {
                    fwrite(STDERR, date('c') . " Failed to create: $adpcmPath\n");
                }
            }
        }
        // part 2
        $wavPath = $audioDir . DIRECTORY_SEPARATOR . $base . '_chat.wav';
        if (!file_exists($wavPath)) {
            // try to create atomically; if another process creates it concurrently, fopen('x') will fail
            $fp = @fopen($wavPath, 'x');
            if ($fp !== false) {
                try {
                    fwrite($fp, "wav 1234567890");
                    fflush($fp);
                } catch (Throwable $e) {
                    echo date('c') . " Error writing to: $wavPath - " . $e->getMessage() . "\n";  
                }
                fclose($fp);
                echo date('c') . " Created: $wavPath\n";
            } else {
                // ignore if already exists, otherwise report
                if (!file_exists($wavPath)) {
                    fwrite(STDERR, date('c') . " Failed to create: $wavPath\n");
                }
            }
        }

    }

    sleep($interval);
}

exit(0);
?>