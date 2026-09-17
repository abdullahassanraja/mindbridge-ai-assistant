"""date_resolution.py
Date awareness, parsing, validation, and resolution for MindBridge Wellness scheduling.

Handles:
1. Awareness of current date and relative date calculation.
2. Ambiguous relative day-of-week detection (e.g. "sunday between 2 and 10pm") -> requires clarification.
3. Already-past date detection relative to today -> requires clarification / correction.
4. Unambiguous future date resolution (e.g. "October 15th at 3pm", "sunday 20 sep between 2 and 10 pm").
5. Confirmation detection when visitor confirms a suggested date.
"""

import re
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any, Tuple

MONTH_MAP = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}

WEEKDAY_MAP = {
    "monday": 0, "mon": 0,
    "tuesday": 1, "tue": 1,
    "wednesday": 2, "wed": 2,
    "thursday": 3, "thu": 3,
    "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5,
    "sunday": 6, "sun": 6,
}

AFFIRM_WORDS = {
    "yes", "yep", "yeah", "sure", "correct", "that's right", "thats right",
    "sounds good", "that works", "perfect", "ok", "okay", "right", "definitely",
    "please", "yes please", "yes that works", "yep that works"
}


def is_affirmative_response(text: str) -> bool:
    """Check if visitor's response is an affirmation without negation."""
    lower = text.lower().strip()
    if re.search(r'\b(no|not|neither|different|wrong|instead|wait)\b', lower):
        return False
    words = set(re.findall(r'\b\w+\b', lower))
    single_word_affirms = {"yes", "yep", "yeah", "sure", "correct", "ok", "okay", "definitely", "perfect", "y"}
    if words & single_word_affirms:
        return True
    multi_word_affirms = [
        "that's right", "thats right", "sounds good", "that works",
        "yes please", "yes that works", "yep that works", "that's fine", "thats fine"
    ]
    return any(phrase in lower for phrase in multi_word_affirms)


def _ordinal_suffix(day: int) -> str:
    """Return ordinal suffix for day: 1st, 2nd, 3rd, 4th, etc."""
    if 11 <= day <= 13:
        return f"{day}th"
    suffix = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    return f"{day}{suffix}"


def get_current_datetime() -> datetime:
    """Get the current datetime."""
    return datetime.now()


def format_date_display(dt: date) -> str:
    """Format a date as 'Sunday, September 20, 2026'."""
    return dt.strftime("%A, %B ") + str(dt.day) + dt.strftime(", %Y")


def format_confirmation_prompt(dt: date) -> str:
    """Format a confirmation prompt like 'Sunday the 20th' or 'Sunday, September 20th'."""
    return f"{dt.strftime('%A')} the {_ordinal_suffix(dt.day)}"


def extract_time_component(text: str) -> Optional[str]:
    """Extract time of day or time range from text."""
    lower = text.lower()

    # 1. Range: between/btw/from X [am/pm] and/to Y [am/pm]
    range_match = re.search(
        r'\b(?:between|btw|from)\s+(\d{1,2}(?::\d{2})?)\s*(am|pm|a\.m\.|p\.m\.)?\s*(?:and|to|-)\s*(\d{1,2}(?::\d{2})?)\s*(am|pm|a\.m\.|p\.m\.)?\b',
        lower
    )
    if range_match:
        start_t = range_match.group(1)
        m1 = range_match.group(2) or ""
        end_t = range_match.group(3)
        m2 = range_match.group(4) or ""
        if m1 and m2:
            return f"between {start_t} {m1} and {end_t} {m2}"
        elif m2:
            return f"between {start_t} and {end_t} {m2}"
        else:
            return f"between {start_t} and {end_t}"

    # 2. Specific time: at 3pm, 3:30 pm, 10am
    time_match = re.search(r'\b(?:at\s+)?(\d{1,2}(?::\d{2})?\s*(?:am|pm|a\.m\.|p\.m\.|o\'?clock))\b', lower)
    if time_match:
        return time_match.group(1).strip()

    # 3. Casual time phrase: morning, afternoon, evening, night
    time_words = re.search(r'\b(morning|afternoon|evening|night|midday|noon)\b', lower)
    if time_words:
        return time_words.group(1).strip()

    # 4. After/before/around X
    after_match = re.search(r'\b(after|before|around)\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\b', lower)
    if after_match:
        return f"{after_match.group(1)} {after_match.group(2)}".strip()

    return None


def resolve_scheduling_input(
    user_text: str,
    current_dt: Optional[datetime] = None,
    pending_candidate_date: Optional[str] = None,
    clarification_mode: Optional[str] = None,
) -> Dict[str, Any]:
    """Analyze visitor input for date/time mentions, check past/ambiguous status,

    and resolve to an unambiguous target date.

    Returns dict with keys:
    - has_timing: bool (True if a timing reference was identified or confirmed)
    - status: 'confirmed' | 'needs_clarification_ambiguous' | 'rejected_past' | 'none'
    - resolved_date: Optional[str] (e.g. "Sunday, September 20, 2026")
    - resolved_full: Optional[str] (e.g. "Sunday, September 20, 2026 (between 2 and 10pm)")
    - suggested_confirmation: Optional[str] (e.g. "Sunday the 20th")
    - raw_input: str
    - explanation: str
    """
    if current_dt is None:
        current_dt = get_current_datetime()

    today = current_dt.date()
    lower = user_text.lower().strip()
    cleaned_punc = re.sub(r'[^\w\s/:.-]', ' ', lower)

    # -------------------------------------------------------------------------
    # 0. Check if visitor is confirming a pending ambiguous date clarification
    # -------------------------------------------------------------------------
    if clarification_mode == "confirm_day" and pending_candidate_date:
        is_affirming = is_affirmative_response(lower)
        # Or if they mentioned the day number matching the candidate date
        day_number_match = re.search(r'\b(\d{1,2})(?:st|nd|rd|th)?\b', lower)
        candidate_has_number = bool(day_number_match and str(day_number_match.group(1)) in pending_candidate_date)

        if is_affirming or candidate_has_number:
            time_part = extract_time_component(user_text)
            full_resolved = pending_candidate_date
            if time_part and time_part not in full_resolved:
                full_resolved = f"{pending_candidate_date} ({time_part})"
            return {
                "has_timing": True,
                "status": "confirmed",
                "resolved_date": pending_candidate_date,
                "resolved_full": full_resolved,
                "suggested_confirmation": None,
                "raw_input": user_text,
                "explanation": f"Visitor confirmed the suggested date: {pending_candidate_date}",
            }

    # -------------------------------------------------------------------------
    # 1. Detect explicit past words
    # -------------------------------------------------------------------------
    past_relative_patterns = [
        r'\byesterday\b',
        r'\blast\s+(?:week|month|year|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b',
        r'\b(?:earlier|past|ago)\b',
    ]
    for pat in past_relative_patterns:
        if re.search(pat, lower):
            return {
                "has_timing": True,
                "status": "rejected_past",
                "resolved_date": None,
                "resolved_full": None,
                "suggested_confirmation": None,
                "raw_input": user_text,
                "explanation": f"Visitor referenced a past date/time frame ('{user_text}').",
            }

    # -------------------------------------------------------------------------
    # 2. Check for explicit calendar date: Month + Day, Day + Month, or MM/DD
    # -------------------------------------------------------------------------
    explicit_month_day: Optional[Tuple[int, int, Optional[int]]] = None # (month, day, year)

    # Pattern A: Day Month [Year] e.g. "20 september", "20th september", "20 sep 2026", "20th of october"
    p_day_month = re.search(
        r'\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?([a-z]+)(?:\s+(\d{4}))?\b',
        lower
    )
    if p_day_month:
        d_val = int(p_day_month.group(1))
        m_str = p_day_month.group(2)
        y_val = int(p_day_month.group(3)) if p_day_month.group(3) else None
        if m_str in MONTH_MAP and 1 <= d_val <= 31:
            explicit_month_day = (MONTH_MAP[m_str], d_val, y_val)

    # Pattern B: Month Day [Year] e.g. "september 20", "oct 15th", "october 15, 2026"
    if not explicit_month_day:
        p_month_day = re.search(
            r'\b([a-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?(?:\s*,?\s*(\d{4}))?\b',
            lower
        )
        if p_month_day:
            m_str = p_month_day.group(1)
            d_val = int(p_month_day.group(2))
            y_val = int(p_month_day.group(3)) if p_month_day.group(3) else None
            if m_str in MONTH_MAP and 1 <= d_val <= 31:
                explicit_month_day = (MONTH_MAP[m_str], d_val, y_val)

    # Pattern C: Numeric MM/DD or MM-DD or MM/DD/YYYY
    if not explicit_month_day:
        p_num_date = re.search(r'\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b', lower)
        if p_num_date:
            m_val = int(p_num_date.group(1))
            d_val = int(p_num_date.group(2))
            raw_y = p_num_date.group(3)
            y_val = None
            if raw_y:
                y_val = int(raw_y) if len(raw_y) == 4 else 2000 + int(raw_y)
            if 1 <= m_val <= 12 and 1 <= d_val <= 31:
                explicit_month_day = (m_val, d_val, y_val)

    if explicit_month_day:
        month, day, year = explicit_month_day
        if not year:
            year = today.year
            # If the month is earlier in the year than current month, it might refer to next year
            # BUT if it's earlier in the current month or recent past, visitor is likely citing a past date
            if month < today.month:
                year = today.year  # evaluate as this year to detect past dates accurately

        try:
            target_date = date(year, month, day)
        except ValueError:
            target_date = None

        if target_date:
            time_part = extract_time_component(user_text)
            date_display = format_date_display(target_date)
            full_display = f"{date_display} ({time_part})" if time_part else date_display

            if target_date < today:
                return {
                    "has_timing": True,
                    "status": "rejected_past",
                    "resolved_date": date_display,
                    "resolved_full": full_display,
                    "suggested_confirmation": None,
                    "raw_input": user_text,
                    "explanation": f"The date {date_display} has already passed relative to today ({format_date_display(today)}).",
                }
            else:
                # Unambiguous specific future date
                return {
                    "has_timing": True,
                    "status": "confirmed",
                    "resolved_date": date_display,
                    "resolved_full": full_display,
                    "suggested_confirmation": None,
                    "raw_input": user_text,
                    "explanation": f"Specific future date confirmed: {full_display}",
                }

    # -------------------------------------------------------------------------
    # 3. Check for "today" or "tomorrow"
    # -------------------------------------------------------------------------
    if re.search(r'\btomorrow\b', lower):
        target_date = today + timedelta(days=1)
        time_part = extract_time_component(user_text)
        date_display = format_date_display(target_date)
        full_display = f"{date_display} ({time_part})" if time_part else date_display
        return {
            "has_timing": True,
            "status": "confirmed",
            "resolved_date": date_display,
            "resolved_full": full_display,
            "suggested_confirmation": None,
            "raw_input": user_text,
            "explanation": f"Resolved 'tomorrow' to {date_display}",
        }

    if re.search(r'\btoday\b', lower):
        time_part = extract_time_component(user_text)
        date_display = format_date_display(today)
        full_display = f"{date_display} ({time_part})" if time_part else date_display
        return {
            "has_timing": True,
            "status": "confirmed",
            "resolved_date": date_display,
            "resolved_full": full_display,
            "suggested_confirmation": None,
            "raw_input": user_text,
            "explanation": f"Resolved 'today' to {date_display}",
        }

    # -------------------------------------------------------------------------
    # 4. Check for Day of Week without numeric date -> Ambiguous Weekday!
    # -------------------------------------------------------------------------
    weekday_match = None
    for name, day_idx in WEEKDAY_MAP.items():
        if re.search(rf'\b{name}\b', lower):
            weekday_match = (name, day_idx)
            break

    if weekday_match:
        day_name, target_idx = weekday_match
        current_idx = today.weekday()

        # Calculate upcoming date for this weekday
        # e.g., if today is Thursday (3) and target is Sunday (6), days_ahead = 3 -> Sunday Sep 20
        days_ahead = (target_idx - current_idx) % 7
        if days_ahead == 0:
            # If they say "Sunday" and today is Sunday, or "next Sunday", bump 7 days
            days_ahead = 7
        elif "next " + day_name in lower and days_ahead < 7:
            # If today is Thursday and they say "next Tuesday", days_ahead = 5 (Tuesday Sep 22)
            pass

        candidate_date = today + timedelta(days=days_ahead)
        date_display = format_date_display(candidate_date)
        time_part = extract_time_component(user_text)
        full_display = f"{date_display} ({time_part})" if time_part else date_display
        confirm_phrase = format_confirmation_prompt(candidate_date)

        return {
            "has_timing": True,
            "status": "needs_clarification_ambiguous",
            "resolved_date": date_display,
            "resolved_full": full_display,
            "suggested_confirmation": confirm_phrase,
            "raw_input": user_text,
            "explanation": f"Visitor gave relative day of week '{day_name}'. Requires clarification to confirm {confirm_phrase}.",
        }

    # -------------------------------------------------------------------------
    # 5. Check if visitor gave ONLY a time of day with no day/date at all
    # -------------------------------------------------------------------------
    time_part = extract_time_component(user_text)
    if time_part and any(w in lower for w in ["at", "pm", "am", "morning", "afternoon", "evening", "between"]):
        # Has a time but no day/date
        return {
            "has_timing": True,
            "status": "needs_clarification_ambiguous",
            "resolved_date": None,
            "resolved_full": time_part,
            "suggested_confirmation": None,
            "raw_input": user_text,
            "explanation": f"Visitor provided a time ({time_part}) but no day or date.",
        }

    return {
        "has_timing": False,
        "status": "none",
        "resolved_date": None,
        "resolved_full": None,
        "suggested_confirmation": None,
        "raw_input": user_text,
        "explanation": "No date or time mention detected.",
    }
