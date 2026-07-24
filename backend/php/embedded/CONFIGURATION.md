# Configuration file examples

## JWT Configuration (/var/www/files/platane/config.ini)

```ini
[JWT]
key = your-32-byte-hex-encoded-key-here
relatedTo = your-app-name
issuedBy = your-organization

[SENSOR]
# For local Ollama (not used in this version but kept for compatibility)
chaturl = http://localhost:11434/api/chat
chatkey = not-needed-for-local-ollama
chatmodel = granite4.1:3b
```

## Devices Configuration (/var/www/files/platane/devices.json)

```json
{
  "sensor001": "a1b2c3d4e5f6",
  "sensor002": "f6e5d4c3b2a1",
  "sensor003": "1234567890abcdef"
}
```

Each sensor ID maps to a hex-encoded key used for challenge-response authentication.

## Apache Configuration (Optional)

If you want to serve this through Apache:

```apache
<VirtualHost *:80>
    ServerName your-domain.com
    DocumentRoot /home/agent/projects/orinchat/platansense/backend-php-rag
    
    <Directory /home/agent/projects/orinchat/platansense/backend-php-rag>
        Options -Indexes +FollowSymLinks
        AllowOverride All
        Require all granted
        
        # Protect audio and data directories
        <FilesMatch "^(audio|data)/">
            Require all denied
        </FilesMatch>
    </Directory>
    
    ErrorLog ${APACHE_LOG_DIR}/rag_backend_error.log
    CustomLog ${APACHE_LOG_DIR}/rag_backend_access.log combined
</VirtualHost>
```

## Nginx Configuration (Optional)

If you want to serve this through Nginx:

```nginx
server {
    listen 80;
    server_name your-domain.com;
    root /home/agent/projects/orinchat/platansense/backend-php-rag;
    index index.php index.html;

    location / {
        try_files $uri $uri/ /index.php?$query_string;
    }

    location ~ \.php$ {
        include fastcgi_params;
        fastcgi_pass unix:/var/run/php/php8.0-fpm.sock;
        fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name;
    }

    # Protect audio and data directories
    location ~ ^/(audio|data)/ {
        deny all;
        return 404;
    }
}
```

## Systemd Service for Ollama (Optional)

Create `/etc/systemd/system/ollama.service`:

```ini
[Unit]
Description=Ollama Service
After=network.target

[Service]
Type=simple
User=your-user
ExecStart=/usr/local/bin/ollama serve
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable ollama
sudo systemctl start ollama
```

## Cron Jobs for Maintenance

Add to crontab (`crontab -e`):

```crontab
# Clean old audio files daily at 3 AM
0 3 * * * find /home/agent/projects/orinchat/platansense/backend-php-rag/audio -type f -mtime +1 -delete

# Clean stale conversation files weekly on Sunday at 4 AM
0 4 * * 0 find /home/agent/projects/orinchat/platansense/backend-php-rag/data -name "*_conversation.json" -mtime +7 -delete

# Restart Ollama if it crashes (check every 5 minutes)
*/5 * * * * pgrep -x ollama > /dev/null || ollama serve > /dev/null 2>&1 &
```