# The caddy-base image: the official caddy image's Alpine layer without the Caddy binary.
# Packages, directories, default Caddyfile, welcome page, environment, ports, workdir and
# CMD follow upstream (https://github.com/caddyserver/caddy-docker, 2.11/alpine/Dockerfile);
# only the binary download is left out. Image repos' slim stages copy their custom-built
# binary onto it.
#
# The Alpine tag below is the one pin. The build workflow derives the `alpine<tag>` alias
# from it and the daily check rebuilds when library/alpine:<tag> is republished.
FROM alpine:3.23

RUN apk add --no-cache \
	ca-certificates \
	curl \
	libcap \
	mailcap

RUN set -eux; \
	mkdir -p \
		/config/caddy \
		/data/caddy \
		/etc/caddy \
		/usr/share/caddy \
	; \
	chmod 1777 /config/caddy /data/caddy; \
	wget -O /etc/caddy/Caddyfile "https://github.com/caddyserver/dist/raw/33ae08ff08d168572df2956ed14fbc4949880d94/config/Caddyfile"; \
	wget -O /usr/share/caddy/index.html "https://github.com/caddyserver/dist/raw/33ae08ff08d168572df2956ed14fbc4949880d94/welcome/index.html"

# See https://caddyserver.com/docs/conventions#file-locations for details
ENV XDG_CONFIG_HOME=/config
ENV XDG_DATA_HOME=/data

EXPOSE 80
EXPOSE 443
EXPOSE 443/udp
EXPOSE 2019

WORKDIR /srv

CMD ["caddy", "run", "--config", "/etc/caddy/Caddyfile", "--adapter", "caddyfile"]
