<?php

// Load configuration
$config = parse_ini_file('/var/www/files/platane/config.ini', true);
if (!$config || !isset($config['SENSOR']['play_cmd'])) {
    echo "Config invalid";
    exit;
}


// Set up signal handler for Ctrl-C (SIGINT)
$should_exit = false;
pcntl_signal(SIGINT, function() {
    global $should_exit;
    echo "\nTerminating signal capture handler...\n";
    $should_exit = true;
});

// Enable async signals
pcntl_async_signals(true);

// Open socket to listen on port 9999
$socket = socket_create(AF_INET, SOCK_STREAM, SOL_TCP);
socket_set_option($socket, SOL_SOCKET, SO_RCVTIMEO, ['sec' => 1, 'usec' => 0]);
if ($socket === false) {
    echo "Failed to create socket\n";
    exit(1);
}

if (!socket_bind($socket, 'localhost', 9999)) {
    echo "Failed to bind socket\n";
    socket_close($socket);
    exit(1);
}

if (!socket_listen($socket, 1)) {
    echo "Failed to listen on socket\n";
    socket_close($socket);
    exit(1);
}

echo "Listening for signals on localhost:9999...\n";

// Loop to capture signals
while (!$should_exit) {
    // Accept incoming connections
    $connection = socket_accept($socket);
    if ($connection === false) {
        if (socket_last_error() === SOCKET_EINTR) {
            continue;
        }
        continue;
    }

    // Read data from connection
    $data = socket_read($connection, 1024);
    if ($data) {
        $signal = trim($data);
        echo "Signal captured: " . $signal . "\n";

        if (strpos($signal, "bye") === 0) {
            $soundFile = __DIR__ . "/data/byebye.wav";
        } else {
            $soundFile = __DIR__ . "/data/greeting.wav";
        }
        
        if (file_exists($soundFile)) {
            // Play the sound using the command from config
            $play_cmd = $config['SENSOR']['play_cmd'];
            $command = escapeshellcmd($play_cmd . ' ' . $soundFile);
            exec($command);
        } else {
            echo "Sound file not found: " . $soundFile . "\n"; 
        }
    }

    socket_close($connection);
}

socket_close($socket);
?>
