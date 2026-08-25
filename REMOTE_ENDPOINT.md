# Remote endpoint architecture

The first remote endpoint keeps Peter headless and moves microphone/speaker ownership to the client device.

## Ownership model

```text
agent shell + identity + memory + session state       Peter
reasoning core adapter                                Peter
Whisper STT + Kokoro/ElevenLabs TTS                  Peter
microphone + speaker + hold-to-talk UI                phone/browser
network transport                                     Tailscale HTTPS
```

The endpoint device is deliberately disposable. Replacing an iPhone with a laptop, Pi, tablet, or another browser does not change the agent.

## First bring-up

After the universal branches are current:

```bash
cd ~/universal-agent
./fullstack-agent/verify-endpoint.sh
```

That verification does not need VM audio hardware. It runs a complete synthetic round trip:

1. starts the loopback endpoint on a temporary port
2. verifies the PWA and endpoint status API
3. sends a text turn through the selected core
4. synthesizes the response with Peter's TTS
5. feeds that WAV back through the same endpoint as if it came from a browser
6. decodes it with ffmpeg and transcribes it with Peter's Whisper model
7. sends the transcript through the selected core
8. synthesizes a second WAV

A pass ends with:

```text
REMOTE_ENDPOINT_VERIFIED: no VM microphone or speaker required.
```

## Start the actual endpoint

```bash
./fullstack-agent/endpoint.sh start
```

This binds only to `127.0.0.1:8787`.

For private phone access over the tailnet:

```bash
./fullstack-agent/endpoint.sh start --tailscale
```

The helper asks Tailscale Serve to publish the loopback service over tailnet-only HTTPS. Check the resulting address with:

```bash
./fullstack-agent/endpoint.sh status
```

Open the HTTPS `*.ts.net` address on the iPhone. HTTPS is required for browser microphone access.

## Persistent service

Once the interactive test is good:

```bash
./fullstack-agent/endpoint.sh install-user-service --tailscale
```

This creates a user systemd unit for the local endpoint. For boot-before-login operation, the helper prints the one-time `loginctl enable-linger` command instead of silently changing that host policy.

## Operations

```bash
./fullstack-agent/endpoint.sh status
./fullstack-agent/endpoint.sh logs
./fullstack-agent/endpoint.sh stop
```

## Security

The endpoint process is loopback-only. Tailscale Serve is the intended HTTPS boundary. Tailnet ACLs should decide which devices can reach Peter. Do not use Funnel for the normal personal endpoint because Funnel exposes the service to the public internet.

The first implementation intentionally does not add a second password layer. A future multi-user or customer-hosted version should add explicit endpoint pairing and per-device identity rather than relying on a shared browser secret.

## Capacity

Only one reasoning turn is allowed at a time in the endpoint process, preserving a coherent agent session. Multiple clients can load the UI, but simultaneous turns serialize rather than racing the selected core.

Whisper and Kokoro stay on Peter, so client devices remain lightweight. The endpoint status payload exposes host memory totals and available memory, and the endpoint verifier prints final system memory plus total loop time. Those measurements are the basis for deciding whether Peter needs more RAM or CPU before adding concurrent endpoints, larger Whisper models, or heavier local cores.
