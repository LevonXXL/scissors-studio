# Include inside scissors.group's HTTPS server {} before location /.
location = /analytics/beacon/ {
    limit_req zone=scissors_beacon burst=10 nodelay;
    limit_req_status 429;
    client_max_body_size 1k;
    access_log /var/log/angie/scissors-beacon.access scissors_analytics_beacon;
    proxy_pass http://127.0.0.1:8553;
    proxy_set_header Host api.studio.scissors.group;
    proxy_set_header X-Forwarded-Proto $scheme;
}
