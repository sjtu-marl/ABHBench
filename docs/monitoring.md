# Self-hosted Monitoring Services (Optional)

If you want to use Langfuse or ClearML for monitoring and tracking, you can deploy your own services:

## Langfuse

Deploy Langfuse using Docker Compose by following the official guide:
https://langfuse.com/self-hosting/deployment/docker-compose

After deployment, add the following environment variables to your `.env` file:

```
LANGFUSE_PUBLIC_KEY=pk-lf-your-public-key
LANGFUSE_SECRET_KEY=sk-lf-your-secret-key
LANGFUSE_HOST=http://localhost:3000

# OpenTelemetry endpoint for Langfuse
OTEL_EXPORTER_OTLP_ENDPOINT=${LANGFUSE_HOST}/api/public/otel
```

You can find your API keys in the Langfuse project settings.

## ClearML

Deploy ClearML server by following the official guide:
https://clear.ml/docs/latest/docs/deploying_clearml/clearml_server_linux_mac

After deployment, configure ClearML by running `clearml-init` and setting up your credentials.
