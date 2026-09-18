from pathlib import Path
import pandas as pd


class RedNewsFilter:
    def __init__(self, calendar_path: str = "news/calendar.csv", blackout_minutes: int = 10):
        self.blackout_minutes = blackout_minutes
        path = Path(calendar_path)
        if path.exists():
            self.events = pd.read_csv(path)
            if not self.events.empty:
                self.events["timestamp_utc"] = pd.to_datetime(self.events["timestamp_utc"], utc=True)
                self.events["impact"] = self.events["impact"].astype(str).str.upper()
                self.events = self.events[self.events["impact"] == "RED"].copy()
        else:
            self.events = pd.DataFrame(columns=["timestamp_utc", "event", "impact"])

    def blocked(self, timestamp) -> tuple[bool, str]:
        ts = pd.Timestamp(timestamp, tz="UTC") if pd.Timestamp(timestamp).tzinfo is None else pd.Timestamp(timestamp).tz_convert("UTC")
        if self.events.empty:
            return False, ""
        delta = (self.events["timestamp_utc"] - ts).abs()
        mask = delta <= pd.Timedelta(minutes=self.blackout_minutes)
        if mask.any():
            event = self.events.loc[mask].iloc[0]
            return True, f"RED NEWS: {event['event']}"
        return False, ""
