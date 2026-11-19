# Link Health

<img src="https://doover.com/wp-content/uploads/Doover-Logo-Landscape-Navy-padded-small.png" alt="App Icon" style="max-width: 300px;">

**See whether a remote field node is still reporting, and how healthy its link and power supply are.**

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/getdoover/link-health/blob/main/LICENSE)

[Configuration](#configuration) • [Tags](#tags) • [Channels](#channels) • [Need Help?](#need-help)

<br/>

## Overview

Link Health is a cloud processor for a **remote field node** — a radio, LoRa, serial or other node whose reports reach Doover through a gateway, a bridge app or another device. It reads the communications and power values the node relays in its messages and turns them into a status, a battery state and a link-quality picture on the device page.

It is about the node behind the gateway, not the Doover device's own connection: the device can be online while the node it relays has gone quiet. It is read-only and sends nothing to the node.

Key capabilities:

- **Reporting status** — `Online`, `Late` or `Offline` from how long ago the node last reported, against its expected report interval. A node that has never reported reads `No data yet`, never Offline.
- **Battery** — the node's battery or supply voltage, coloured Low / Normal / High against configurable limits (defaults 9.5–14.5 V, so a 12 V system charging normally at 13–14 V reads Normal).
- **Link quality** — link success rate as a gauge (Good / Fair / Poor), plus a rolling 24 h average, from either a reported percentage or success / attempt counters.
- **Signal and route** — retries, RSSI, optional SNR, and the route or hop path the reports take.
- **Notifications** — node offline and battery low by default; battery high and poor link for those who opt in.
- **Scheduled checks** — re-checks every 5 minutes (configurable), so Late and Offline are detected without waiting for a message.

<br/>

## Configuration

Every input is a **message path**, `$<channel>.<path.to.value>`, read from messages on the subscribed channels. Leave a path empty if the node does not report that value; its UI element is hidden.

| Setting | Description | Default |
|---------|-------------|---------|
| **Battery Voltage Path** | Battery or supply voltage (V) | `$io_state.battery_v` |
| **Link Success Path** | Link success rate (0–100 %) | `$io_state.link_success_pct` |
| **Success Count Path** | Count of successful transmissions (use with Attempt Count Path) | *empty* |
| **Attempt Count Path** | Count of attempted transmissions | *empty* |
| **Counter Type** | `Cumulative` running totals (a drop is read as a reset) or `Per report` counts | `Cumulative` |
| **Retries Path** | Retry count | `$io_state.retries` |
| **Signal Strength (RSSI) Path** | Received signal strength (dBm) | `$io_state.rssi` |
| **Signal-to-Noise (SNR) Path** | Signal-to-noise ratio (dB) | *empty* |
| **Route Path** | Text, or a list of hops, describing the route | `$io_state.route` |
| **Last Heard Path** | Time the node was last heard: epoch seconds, epoch ms or ISO 8601. Without it, the message arrival time is used | `$io_state.last_heard` |
| **Expected Report Interval (min)** | How often the node should report | `15` |
| **Late After (intervals)** | Late once the last report is older than this many intervals | `2` |
| **Offline After (intervals)** | Offline once the last report is older than this many intervals | `4` |
| **Battery Low (V)** | Below this reads Low | `9.5` |
| **Battery High (V)** | Above this reads High | `14.5` |
| **Link Success Warning (%)** | Below this reads Fair | `80` |
| **Link Success Poor (%)** | Below this reads Poor | `50` |
| **Subscription** *(advanced)* | Channels to read messages from | `["io_state"]` |
| **Schedule** *(advanced)* | How often to re-check the status without a message | `rate(5 minutes)` |
| **Position** *(hidden)* | Where the app sits on the device page; smaller is higher. Defaults low on the page | `900` |
| **Default Open** *(hidden)* | Whether the app's panel starts expanded | `false` |

A message counts as a report from the node only when it carries at least one configured value. A report older than the last one (by its last-heard time) is ignored, so a replayed message cannot move the status backwards.

When both a percentage and counters are configured, the reported percentage is shown and the counters feed the 24 h average.

<br/>

## Tags

| Tag | Description |
|-----|-------------|
| `status` | `online`, `late`, `offline` or `unknown` (never heard) |
| `last_heard_ts` | Time of the node's last report (epoch ms) |
| `battery_v` | Battery or supply voltage (V) |
| `battery_state` | `normal`, `low` or `high` |
| `link_success_pct` | Latest link success rate (%) |
| `link_success_24h_pct` | Link success over the last 24 h (%) — the mean of reported percentages, or successes ÷ attempts from counters |
| `link_quality` | `good`, `fair` or `poor` |
| `retries` | Latest retry count |
| `rssi` | Latest RSSI (dBm) |
| `snr` | Latest SNR (dB) |
| `route` | Route / hop description |

Every value tag stays empty until the node reports it.

<br/>

## Notifications

| Notification | Sent when | Policy |
|--------------|-----------|--------|
| **Node offline** | The node goes from Online or Late to Offline | Default |
| **Battery low** | The voltage drops below Battery Low | Default |
| **Battery high** | The voltage rises above Battery High | Opt-in |
| **Poor link** | Link success drops below Link Success Poor | Opt-in |

Each is sent once per transition, not on every report. With no data nothing is sent.

<br/>

## Channels

- **Inputs** — the channels in **Subscription** (default `io_state`), read at the configured message paths. Any source can write them: a bridge app on a Doovit, a LoRaWAN integration, another device.
- **Outputs** — this app's tags in `tag_values`, and notifications on the `notifications` channel. It sends no commands.

Example input message on `io_state`:

```json
{
  "battery_v": 13.6,
  "link_success_pct": 94,
  "retries": 2,
  "rssi": -96,
  "route": ["Node 7", "Repeater", "Gateway"],
  "last_heard": 1795050000
}
```

<br/>

## Need Help?

- Email: support@doover.com
- [Community Forum](https://doover.com/community)
- [Full Documentation](https://docs.doover.com)

<br/>

## License

This app is licensed under the [Apache License 2.0](https://github.com/getdoover/link-health/blob/main/LICENSE).
