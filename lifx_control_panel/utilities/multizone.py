# -*- coding: utf-8 -*-
"""Setting per-zone colors on multizone devices (Beam, Z strip).

The pinned lifxlan fork only speaks the legacy SetColorZones (501), which carries one color
range per UDP packet. A LIFX device absorbs about 20 messages a second; painting a 61-zone
Beam zone-by-zone pushes ~90/s, its queue overflows, and it then stops answering *everything*
-- acks, zone reads, even GetPower -- until it's left alone. That's what made per-zone editing
look like it "works once and never again".

SetExtendedColorZones (510, firmware 2.77+) carries up to 82 zones in a single packet, so a
whole strip costs one acked message.
"""

import bitstring
import lifxlan
from lifxlan.message import Message, little_endian
from lifxlan.msgtypes import GetHostFirmware, StateHostFirmware

MAX_EXTENDED_ZONES = 82

APPLY = 1  # apply this message's zones immediately, plus any pending ones

# lifxlan's req_with_ack sends once and waits a second. Measured against a Beam on a weak
# link, ~1 message in 5 is lost, in bursts long enough that two tries a second apart both
# miss -- so a commit needs several seconds of retrying, which is why callers run it off
# the GUI thread rather than blocking tkinter.
DEFAULT_ATTEMPTS = 2


class SetExtendedColorZones(Message):
    """LIFX message 510. `colors` is padded to the fixed-length 82-color array on the wire."""

    def __init__(
        self,
        target_addr,
        source_id,
        seq_num,
        payload,
        ack_requested=False,
        response_requested=False,
    ):
        self.duration = payload["duration"]
        self.apply = payload["apply"]
        self.zone_index = payload["zone_index"]
        self.colors = payload["colors"]
        super().__init__(
            510, target_addr, source_id, seq_num, ack_requested, response_requested
        )

    def get_payload(self):
        self.payload_fields.append(("Duration", self.duration))
        self.payload_fields.append(("Apply", self.apply))
        self.payload_fields.append(("Zone Index", self.zone_index))
        self.payload_fields.append(("Colors", self.colors))
        payload = (
            little_endian(bitstring.pack("32", self.duration))
            + little_endian(bitstring.pack("8", self.apply))
            + little_endian(bitstring.pack("16", self.zone_index))
            + little_endian(bitstring.pack("8", len(self.colors)))
        )
        padded = list(self.colors) + [(0, 0, 0, 0)] * (
            MAX_EXTENDED_ZONES - len(self.colors)
        )
        for color in padded:
            payload += b"".join(
                little_endian(bitstring.pack("16", field)) for field in color
            )
        return payload


def supports_extended(target):
    """Whether the device's firmware knows message 510, asked once and cached per device.

    Deliberately *not* probed by sending a 510 and watching for an ack: a busy device drops
    acks for a second or two, and treating that as "old firmware" would pin a capable Beam to
    the legacy path -- the very flood that overloads it. Firmware version doesn't flap.

    lifxlan's own get_host_firmware_version() can't answer this: it builds a float from
    "major.minor", so firmware 2.8 reads as 2.8 and compares *above* the 2.77 cutoff.
    """
    cached = getattr(target, "supports_extended_multizone", None)
    if cached is not None:
        return cached
    try:
        response = target.req_with_resp(GetHostFirmware, StateHostFirmware)
    except lifxlan.WorkflowException:
        # Unknown for now; ask again next time. Assume yes meanwhile -- one packet is the
        # guess that can't make a struggling device worse.
        return True
    target.supports_extended_multizone = (
        response.version >> 16,
        response.version & 0xFFFF,
    ) >= (2, 77)
    return target.supports_extended_multizone


def set_zone_colors(target, colors, duration=0, attempts=DEFAULT_ATTEMPTS):
    """Push a full list of per-zone HSBK colors to a multizone device.

    One packet via extended multizone where possible, otherwise one acked legacy message per
    run of equal-colored zones. Raises WorkflowException if the device never acknowledged.
    """
    if len(colors) > MAX_EXTENDED_ZONES or not supports_extended(target):
        _set_zone_colors_legacy(target, colors, duration, attempts)
        return
    payload = {
        "duration": duration,
        "apply": APPLY,
        "zone_index": 0,
        "colors": [tuple(color) for color in colors],
    }
    error = None
    for attempt in range(attempts):
        try:
            return target.req_with_ack(SetExtendedColorZones, payload)
        except lifxlan.WorkflowException as exc:
            error = exc
    raise error


def _set_zone_colors_legacy(target, colors, duration=0, attempts=DEFAULT_ATTEMPTS):
    """Fallback for pre-2.77 firmware and strips longer than 82 zones.

    Equal neighbouring zones coalesce into one acked SetColorZones, and a run that doesn't ack
    is retried once because lifxlan's req_with_ack gives up after a single attempt.
    """
    runs = []
    for index, color in enumerate(colors):
        if runs and tuple(runs[-1][2]) == tuple(color):
            runs[-1][1] = index  # protocol end_index is INCLUSIVE
        else:
            runs.append([index, index, color])
    error = None
    for start, end, color in runs:
        # ponytail: every run applies immediately rather than buffering with apply=0 and one
        # final apply -- a dropped run can't then strand the rest of the strip unapplied.
        for attempt in range(attempts):
            try:
                target.set_zone_color(start, end, color, duration)
                break
            except lifxlan.WorkflowException as exc:
                error = exc
    if error is not None:
        raise error
