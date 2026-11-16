FROM node:24-alpine@sha256:8a32c8cf649a49915a66e81e7a609223c708d0adabf288ee3f4077d765542f85 AS build
WORKDIR /src
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build -- --configuration production
FROM nginx/nginx-unprivileged:stable-alpine@sha256:ea4fd7ab5a8dc6348c18240bd3546f355f8373cd8f112580f7d8bd8ff5a74772
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /src/dist/ui/browser /usr/share/nginx/html
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s CMD wget -q -O /dev/null http://127.0.0.1:8080/healthz || exit 1
