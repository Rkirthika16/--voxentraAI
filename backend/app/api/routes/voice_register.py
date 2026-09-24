# -*- coding: utf-8 -*-
"""
AI Voice Citizen Complaint Registration - Dedicated API
========================================================
Provides clean REST endpoints for the full two-way voice complaint registration flow:
  POST /voice-register/start        - Start session, return greeting
  POST /voice-register/turn         - Submit one dialogue turn (text)
  POST /voice-register/audio-turn   - Submit one dialogue turn (audio upload)
  GET  /voice-register/session/{id} - Poll current session state
  POST /webhooks/exotel/voice/dialogue - Exotel STT callback -> dialogue turn

All flows reuse the existing ComplaintCollector, language_service, classification_service,
and send Twilio SMS on confirmation with full bilingual template support and failure handling.
"""

import os
import uuid
import logging
import aiofiles
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from fastapi import APIRouter, Request, Depends, UploadFile, File, Form, Response
from sqlalchemy.orm import Session

from app.config import settings
from app.database.session import get_db
from app.schemas.ivr import (
    VoiceRegisterStartRequest,
    VoiceRegisterStartResponse,
    VoiceRegisterTurnRequest,
    VoiceRegisterTurnResponse,
    VoiceRegisterSessionResponse
)
from app.ai.complaint_collector import complaint_collector, FIELD_KEYS, FIELD_METADATA

FIELD_KEYS_COUNT = len(FIELD_KEYS)
from app.ai.language_service import detect_language
from app.ai.normalization_service import normalize_text
from app.ai.classification_service import classify_complaint
from app.ai.location_service import extract_location
from app.integrations.telephony.twilio_adapter import twilio_adapter
from app.utils.validators import validate_audio_file
from app.core.exceptions import BadRequestException

logger = logging.getLogger("voxentra.voice_register")

router = APIRouter(tags=["AI Voice Complaint Registration"])


def _count_collected(session: Dict[str, Any]) -> int:
    """Count how many of the 10 required fields have been collected."""
    return sum(
        1 for k in FIELD_KEYS
        if session["fields"].get(k) and str(session["fields"][k]).strip()
    )


def _build_greeting(lang: str) -> tuple:
    """Return (greeting_ta, greeting_en, first_question) for opening turn."""
    greeting_ta = (
        "\u0bb5\u0ba3\u0b95\u0bcd\u0b95\u0bae\u0bcd! "
        "\u0bb5\u0bbe\u0b95\u0bcd\u0b9a\u0bc6\u0ba9\u0bcd\u0b9f\u0bcd\u0bb0\u0bbe AI \u0baa\u0bc1\u0b95\u0bbe\u0bb0\u0bcd "
        "\u0baa\u0ba4\u0bbf\u0bb5\u0bc1 \u0b9a\u0bc7\u0bb5\u0bc8\u0b95\u0bcd\u0b95\u0bc1 \u0ba8\u0bb2\u0bcd\u0bb5\u0bb0\u0bb5\u0bc1. "
        "\u0ba4\u0baf\u0bb5\u0bc1\u0b9a\u0bc6\u0baf\u0bcd\u0ba4\u0bc1 \u0b89\u0b99\u0bcd\u0b95\u0bb3\u0bcd \u0baa\u0bbf\u0bb0\u0b9a\u0bcd\u0b9a\u0ba9\u0bc8 "
        "\u0ba4\u0bae\u0bbf\u0bb4\u0bbf\u0bb2\u0bcd, \u0b86\u0b99\u0bcd\u0b95\u0bbf\u0bb2\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd "
        "\u0b85\u0bb2\u0bcd\u0bb2\u0ba4\u0bc1 \u0ba4\u0b99\u0bcd\u0b95\u0bbf\u0bb2\u0bc0\u0bb7\u0bbf\u0bb2\u0bcd \u0b95\u0bc2\u0bb1\u0bb2\u0bbe\u0bae\u0bcd."
    )
    greeting_en = (
        "Welcome! This is VoxentraAI Voice Complaint Registration. "
        "You may speak in Tamil, English, or Tanglish."
    )
    q_ta = "\u0ba8\u0bc0\u0b99\u0bcd\u0b95\u0bb3\u0bcd \u0b9a\u0ba8\u0bcd\u0ba4\u0bbf\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0baa\u0bc6\u0bbe\u0ba4\u0bc1 \u0baa\u0bbf\u0bb0\u0b9a\u0bcd\u0b9a\u0ba9\u0bc8 \u0b85\u0bb2\u0bcd\u0bb2\u0ba4\u0bc1 \u0baa\u0bc1\u0b95\u0bbe\u0bb0\u0bcd \u0b8e\u0ba9\u0bcd\u0ba9 \u0b8e\u0ba9\u0bcd\u0bb1\u0bc1 \u0b95\u0bc2\u0bb1\u0bb5\u0bc1\u0bae\u0bcd?"
    q_en = "What civic problem or grievance would you like to report?"
    q_tanglish = "Ungaloda problem enna nu sollunga."

    if lang == "Tamil":
        first_q = q_ta
    elif lang == "Tanglish":
        first_q = q_tanglish
    else:
        first_q = q_en

    return greeting_ta, greeting_en, first_q


def _process_dialogue_turn(
    session: Dict[str, Any],
    user_speech: str,
    caller_phone: str,
    db: Session
) -> VoiceRegisterTurnResponse:
    """
    Core logic shared between /turn and /audio-turn.
    Runs one complete dialogue step: detect lang -> extract slots -> check missing -> respond.
    """
    call_sid = session["session_id"]
    dialogue_turn = session.get("dialogue_turn", 1)
    session["dialogue_turn"] = dialogue_turn

    if caller_phone:
        session["caller_phone"] = caller_phone

    # Language detection
    detected_lang, lang_conf = detect_language(user_speech)
    lang_pref = session.get("language_preference", "Auto")
    if lang_pref in ["Tamil", "English", "Tanglish"]:
        detected_lang = lang_pref
        lang_conf = 1.0
    session["language"] = detected_lang

    # --- 0a. Check if session has a pending slot confirmation (misheard word / spelling candidate) ---
    if session.get("pending_slot_confirmation"):
        is_resolved, resolved_val, ack_reply, ack_spoken = complaint_collector.handle_slot_confirmation_turn(
            session, user_speech, detected_lang
        )
        if not is_resolved:
            session["dialogue_turn"] = dialogue_turn + 1
            return VoiceRegisterTurnResponse(
                session_id=call_sid,
                call_sid=call_sid,
                dialogue_turn=dialogue_turn + 1,
                ai_reply=ack_spoken,
                ai_reply_tamil=ack_reply if detected_lang == "Tamil" else ack_spoken,
                ai_reply_english=ack_spoken if detected_lang == "English" else ack_reply,
                detected_language=detected_lang,
                language_confidence=lang_conf,
                intent="SLOT_CONFIRMATION_PENDING",
                fields_collected=_count_collected(session),
                fields_total=FIELD_KEYS_COUNT,
                is_confirmation_pending=False,
                is_completed=False,
                collection_state=session["fields"]
            )
        else:
            # Slot resolved! Check next missing field
            next_missing = complaint_collector.get_next_missing_field(session)
            if not next_missing:
                session["state"] = "CONFIRMATION_PENDING"
                session["current_field_prompted"] = None
                summary_text, spoken_summary = complaint_collector.generate_summary(session, detected_lang)
                session["dialogue_turn"] = dialogue_turn + 1
                return VoiceRegisterTurnResponse(
                    session_id=call_sid,
                    call_sid=call_sid,
                    dialogue_turn=dialogue_turn + 1,
                    ai_reply=f"{ack_spoken} {spoken_summary}",
                    ai_reply_tamil=f"{ack_reply} {summary_text}" if detected_lang == "Tamil" else f"{ack_spoken} {spoken_summary}",
                    ai_reply_english=f"{ack_spoken} {spoken_summary}" if detected_lang == "English" else f"{ack_reply} {summary_text}",
                    detected_language=detected_lang,
                    language_confidence=lang_conf,
                    intent="CONFIRMATION_PENDING",
                    fields_collected=_count_collected(session),
                    fields_total=FIELD_KEYS_COUNT,
                    is_confirmation_pending=True,
                    is_completed=False,
                    collection_state=session["fields"]
                )
            else:
                session["state"] = "COLLECTING"
                session["current_field_prompted"] = next_missing
                q_text, sp_text = complaint_collector.get_contextual_question(session, next_missing, detected_lang)
                q_ta, _ = complaint_collector.get_contextual_question(session, next_missing, "Tamil")
                q_en, _ = complaint_collector.get_contextual_question(session, next_missing, "English")
                session["dialogue_turn"] = dialogue_turn + 1
                return VoiceRegisterTurnResponse(
                    session_id=call_sid,
                    call_sid=call_sid,
                    dialogue_turn=dialogue_turn + 1,
                    ai_reply=f"{ack_spoken} {sp_text}",
                    ai_reply_tamil=f"{ack_reply} {q_ta}" if detected_lang == "Tamil" else f"{ack_spoken} {q_ta}",
                    ai_reply_english=f"{ack_spoken} {q_en}" if detected_lang == "English" else f"{ack_reply} {q_en}",
                    detected_language=detected_lang,
                    language_confidence=lang_conf,
                    intent="GATHER_MORE_INFO",
                    fields_collected=_count_collected(session),
                    fields_total=FIELD_KEYS_COUNT,
                    next_field=next_missing,
                    is_confirmation_pending=False,
                    is_completed=False,
                    collection_state=session["fields"]
                )

    # --- 0b. Check if speech is unclear / misheard / corrupted ---
    if complaint_collector.detect_unclear_speech(user_speech):
        unclear_reply, unclear_spoken = complaint_collector.get_unclear_prompt(detected_lang)
        q_ta, _ = complaint_collector.get_unclear_prompt("Tamil")
        q_en, _ = complaint_collector.get_unclear_prompt("English")
        session["dialogue_turn"] = dialogue_turn + 1
        return VoiceRegisterTurnResponse(
            session_id=call_sid,
            call_sid=call_sid,
            dialogue_turn=dialogue_turn + 1,
            ai_reply=unclear_spoken,
            ai_reply_tamil=q_ta,
            ai_reply_english=q_en,
            detected_language=detected_lang,
            language_confidence=lang_conf,
            intent="UNCLEAR_INPUT",
            fields_collected=_count_collected(session),
            fields_total=FIELD_KEYS_COUNT,
            is_confirmation_pending=False,
            is_completed=False,
            collection_state=session["fields"]
        )

    # --- 1. Confirmation stage ---
    if session.get("state") == "CONFIRMATION_PENDING":
        is_decision, is_confirmed = complaint_collector.is_confirmation_response(user_speech)
        if is_decision:
            if is_confirmed:
                # Register complaint
                created = complaint_collector.register_complaint_record(
                    session, db,
                    call_sid=call_sid,
                    caller_phone=caller_phone,
                    sms_status="PENDING"
                )
                dept_name = created.department.name if created.department else "Municipal Administration"
                problem = session["fields"].get("problem_description", "Civic Grievance")
                location_str = (
                    f"{session['fields'].get('district_area', '')}, "
                    f"{session['fields'].get('street_road_name', '')}"
                ).strip(", ")

                # Build bilingual Twilio SMS
                sms_body = twilio_adapter.build_complaint_sms(
                    complaint_number=created.complaint_number,
                    description=problem,
                    department=dept_name,
                    location=location_str,
                    lang=detected_lang,
                    created_at=created.created_at
                )
                sms_result = twilio_adapter.send_sms(caller_phone or "+919843098765", sms_body)
                sms_sent = sms_result.get("success", False)
                sms_sid = sms_result.get("sid", "")
                sms_err = sms_result.get("error")

                # Update SMS status in complaint's ai_metadata
                if created.ai_metadata:
                    meta = dict(created.ai_metadata)
                    meta["sms_status"] = "SENT" if sms_sent else "FAILED"
                    meta["sms_sid"] = sms_sid
                    meta["sms_sent_at"] = datetime.now(timezone.utc).isoformat() if sms_sent else None
                    created.ai_metadata = meta
                    db.commit()

                # Build spoken confirmation
                if sms_sent:
                    if detected_lang == "Tamil":
                        reply_ta = (
                            f"\u0ba8\u0ba9\u0bcd\u0bb1\u0bbf! \u0b89\u0b99\u0bcd\u0b95\u0bb3\u0bcd \u0baa\u0bc1\u0b95\u0bbe\u0bb0\u0bcd {created.complaint_number} "
                            f"\u0bb5\u0bc6\u0bb1\u0bcd\u0bb1\u0bbf\u0b95\u0bb0\u0bae\u0bbe\u0b95 \u0baa\u0ba4\u0bbf\u0bb5\u0bc1 \u0b9a\u0bc6\u0baf\u0bcd\u0baf\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0ba4\u0bc1. "
                            f"\u0b87\u0ba4\u0bc1 {dept_name} \u0ba4\u0bc1\u0bb1\u0bc8\u0b95\u0bcd\u0b95\u0bc1 \u0b85\u0ba9\u0bc1\u0baa\u0bcd\u0baa\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bc1\u0bb3\u0bcd\u0bb3\u0ba4\u0bc1. "
                            "\u0b89\u0b99\u0bcd\u0b95\u0bb3\u0bcd \u0b95\u0bc8\u0baa\u0bc7\u0b9a\u0bbf\u0b95\u0bcd\u0b95\u0bc1 \u0b8e\u0bb8\u0bcd.\u0b8e\u0bae\u0bcd.\u0b8e\u0bb8\u0bcd \u0b85\u0ba9\u0bc1\u0baa\u0bcd\u0baa\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bc1\u0bb3\u0bcd\u0bb3\u0ba4\u0bc1."
                        )
                        reply_en = f"Complaint {created.complaint_number} registered and forwarded to {dept_name}. SMS sent."
                        spoken = reply_ta
                    elif detected_lang == "Tanglish":
                        reply_ta = f"Thank you! Unga complaint {created.complaint_number} register aagi {dept_name} ku forward panniyaachu. SMS unga mobile ku anupiyachu."
                        reply_en = f"Complaint {created.complaint_number} registered and forwarded to {dept_name}. SMS sent."
                        spoken = reply_ta
                    else:
                        reply_ta = f"\u0baa\u0bc1\u0b95\u0bbe\u0bb0\u0bcd \u0b8e\u0ba3\u0bcd {created.complaint_number} \u0baa\u0ba4\u0bbf\u0bb5\u0bc1 \u0b9a\u0bc6\u0baf\u0bcd\u0baf\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0ba4\u0bc1."
                        reply_en = (
                            f"Thank you! Your complaint has been registered under ID {created.complaint_number} "
                            f"and forwarded to {dept_name}. A confirmation SMS has been sent to your phone."
                        )
                        spoken = reply_en
                else:
                    # SMS failed - still registered, be honest
                    if detected_lang == "Tamil":
                        reply_ta = (
                            f"\u0b89\u0b99\u0bcd\u0b95\u0bb3\u0bcd \u0baa\u0bc1\u0b95\u0bbe\u0bb0\u0bcd \u0bb5\u0bc6\u0bb1\u0bcd\u0bb1\u0bbf\u0b95\u0bb0\u0bae\u0bbe\u0b95 \u0baa\u0ba4\u0bbf\u0bb5\u0bc1 \u0b9a\u0bc6\u0baf\u0bcd\u0baf\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bc1\u0bb3\u0bcd\u0bb3\u0ba4\u0bc1. "
                            f"\u0b86\u0ba9\u0bbe\u0bb2\u0bcd SMS \u0b85\u0ba9\u0bc1\u0baa\u0bcd\u0baa\u0bc1\u0bb5\u0ba4\u0bbf\u0bb2\u0bcd \u0ba4\u0bb1\u0bcd\u0b95\u0bbe\u0bb2\u0bbf\u0b95 \u0b9a\u0bbf\u0b95\u0bcd\u0b95\u0bb2\u0bcd \u0b8f\u0bb1\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bc1\u0bb3\u0bcd\u0bb3\u0ba4\u0bc1. "
                            f"\u0b89\u0b99\u0bcd\u0b95\u0bb3\u0bcd \u0baa\u0bc1\u0b95\u0bbe\u0bb0\u0bcd \u0b8e\u0ba3\u0bcd {created.complaint_number}."
                        )
                        reply_en = f"Complaint {created.complaint_number} registered. SMS delivery failed temporarily."
                        spoken = reply_ta
                    elif detected_lang == "Tanglish":
                        reply_ta = f"Unga complaint {created.complaint_number} register aaiduchu. Aanaa SMS anupuvathil temporary issue. Complaint number: {created.complaint_number}."
                        reply_en = f"Complaint {created.complaint_number} registered. SMS delivery failed temporarily."
                        spoken = reply_ta
                    else:
                        reply_ta = f"\u0baa\u0bc1\u0b95\u0bbe\u0bb0\u0bcd \u0b8e\u0ba3\u0bcd {created.complaint_number} \u0baa\u0ba4\u0bbf\u0bb5\u0bc1 \u0b9a\u0bc6\u0baf\u0bcd\u0baf\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0ba4\u0bc1."
                        reply_en = (
                            f"Your complaint has been successfully registered under ID {created.complaint_number} "
                            f"and forwarded to {dept_name}. However, there was a temporary issue sending the SMS. "
                            f"Your complaint ID is {created.complaint_number}."
                        )
                        spoken = reply_en

                session["dialogue_turn"] = dialogue_turn + 1
                return VoiceRegisterTurnResponse(
                    session_id=call_sid,
                    call_sid=call_sid,
                    dialogue_turn=dialogue_turn + 1,
                    ai_reply=spoken,
                    ai_reply_tamil=reply_ta,
                    ai_reply_english=reply_en,
                    detected_language=detected_lang,
                    language_confidence=lang_conf,
                    intent="CONFIRMED",
                    fields_collected=_count_collected(session),
                    fields_total=FIELD_KEYS_COUNT,
                    is_confirmation_pending=False,
                    is_completed=True,
                    collection_state=session["fields"],
                    complaint_id=created.id,
                    complaint_number=created.complaint_number,
                    sms_sent=sms_sent,
                    sms_failure_reason=sms_err if not sms_sent else None
                )
            else:
                # Citizen wants to edit
                session["state"] = "COLLECTING"
                session["current_field_prompted"] = "problem_description"
                if detected_lang == "Tamil":
                    reply_ta = "\u0b9a\u0bb0\u0bbf, \u0b8e\u0ba8\u0bcd\u0ba4 \u0bb5\u0bbf\u0bb5\u0bb0\u0ba4\u0bcd\u0ba4\u0bc8 \u0bae\u0bbe\u0bb1\u0bcd\u0bb1 \u0bb5\u0bc7\u0ba3\u0bcd\u0b9f\u0bc1\u0bae\u0bcd? \u0ba4\u0baf\u0bb5\u0bc1\u0b9a\u0bc6\u0baf\u0bcd\u0ba4\u0bc1 \u0b95\u0bc2\u0bb1\u0bb5\u0bc1\u0bae\u0bcd."
                    reply_en = "Sure, which detail would you like to update? Please specify."
                    spoken = reply_ta
                elif detected_lang == "Tanglish":
                    reply_ta = "Sure, endha detail ah maathanum nu sollunga."
                    reply_en = "Which detail would you like to update?"
                    spoken = reply_ta
                else:
                    reply_ta = "\u0b8e\u0ba8\u0bcd\u0ba4 \u0bb5\u0bbf\u0bb5\u0bb0\u0ba4\u0bcd\u0ba4\u0bc8 \u0bae\u0bbe\u0bb1\u0bcd\u0bb1 \u0bb5\u0bc7\u0ba3\u0bcd\u0b9f\u0bc1\u0bae\u0bcd?"
                    reply_en = "Understood. Which detail would you like to correct or update?"
                    spoken = reply_en

                session["dialogue_turn"] = dialogue_turn + 1
                return VoiceRegisterTurnResponse(
                    session_id=call_sid,
                    call_sid=call_sid,
                    dialogue_turn=dialogue_turn + 1,
                    ai_reply=spoken,
                    ai_reply_tamil=reply_ta,
                    ai_reply_english=reply_en,
                    detected_language=detected_lang,
                    language_confidence=lang_conf,
                    intent="GATHER_MORE_INFO",
                    fields_collected=_count_collected(session),
                    fields_total=FIELD_KEYS_COUNT,
                    is_confirmation_pending=False,
                    is_completed=False,
                    collection_state=session["fields"]
                )

    # --- 1b. Check for explicit speech or slot correction ---
    explicit_corr = complaint_collector.detect_explicit_correction(session, user_speech, detected_lang)
    if explicit_corr:
        corr_field, new_val, ack_reply, ack_spoken = explicit_corr
        next_missing = complaint_collector.get_next_missing_field(session)
        if not next_missing:
            session["state"] = "CONFIRMATION_PENDING"
            session["current_field_prompted"] = None
            summary_text, spoken_summary = complaint_collector.generate_summary(session, detected_lang)
            session["dialogue_turn"] = dialogue_turn + 1
            return VoiceRegisterTurnResponse(
                session_id=call_sid,
                call_sid=call_sid,
                dialogue_turn=dialogue_turn + 1,
                ai_reply=f"{ack_spoken} {spoken_summary}",
                ai_reply_tamil=f"{ack_reply} {summary_text}" if detected_lang == "Tamil" else f"{ack_spoken} {spoken_summary}",
                ai_reply_english=f"{ack_spoken} {spoken_summary}" if detected_lang == "English" else f"{ack_reply} {summary_text}",
                detected_language=detected_lang,
                language_confidence=lang_conf,
                intent="CORRECTION_APPLIED",
                fields_collected=_count_collected(session),
                fields_total=FIELD_KEYS_COUNT,
                is_confirmation_pending=True,
                is_completed=False,
                collection_state=session["fields"]
            )
        else:
            session["state"] = "COLLECTING"
            session["current_field_prompted"] = next_missing
            q_text, sp_text = complaint_collector.get_contextual_question(session, next_missing, detected_lang)
            q_ta, _ = complaint_collector.get_contextual_question(session, next_missing, "Tamil")
            q_en, _ = complaint_collector.get_contextual_question(session, next_missing, "English")
            session["dialogue_turn"] = dialogue_turn + 1
            return VoiceRegisterTurnResponse(
                session_id=call_sid,
                call_sid=call_sid,
                dialogue_turn=dialogue_turn + 1,
                ai_reply=f"{ack_spoken} {sp_text}",
                ai_reply_tamil=f"{ack_reply} {q_ta}" if detected_lang == "Tamil" else f"{ack_spoken} {q_ta}",
                ai_reply_english=f"{ack_spoken} {q_en}" if detected_lang == "English" else f"{ack_reply} {q_en}",
                detected_language=detected_lang,
                language_confidence=lang_conf,
                intent="CORRECTION_APPLIED",
                fields_collected=_count_collected(session),
                fields_total=FIELD_KEYS_COUNT,
                next_field=next_missing,
                is_confirmation_pending=False,
                is_completed=False,
                collection_state=session["fields"]
            )

    # --- 1c. Check for spelling / recognition candidate variation on current field ---
    current_field = session.get("current_field_prompted")
    if current_field:
        variation_candidate = complaint_collector.find_spelling_or_recognition_variation(current_field, user_speech)
        if variation_candidate:
            session["pending_slot_confirmation"] = {
                "field": current_field,
                "original_input": user_speech,
                "detected_word": variation_candidate
            }
            conf_text, conf_spoken = complaint_collector.get_spelling_or_correction_prompt(variation_candidate, detected_lang)
            q_ta, _ = complaint_collector.get_spelling_or_correction_prompt(variation_candidate, "Tamil")
            q_en, _ = complaint_collector.get_spelling_or_correction_prompt(variation_candidate, "English")
            session["dialogue_turn"] = dialogue_turn + 1
            return VoiceRegisterTurnResponse(
                session_id=call_sid,
                call_sid=call_sid,
                dialogue_turn=dialogue_turn + 1,
                ai_reply=conf_spoken,
                ai_reply_tamil=q_ta,
                ai_reply_english=q_en,
                detected_language=detected_lang,
                language_confidence=lang_conf,
                intent="SLOT_CONFIRMATION_PENDING",
                fields_collected=_count_collected(session),
                fields_total=FIELD_KEYS_COUNT,
                is_confirmation_pending=False,
                is_completed=False,
                collection_state=session["fields"]
            )

    # --- Slot extraction ---
    import re
    current_field = session.get("current_field_prompted")
    extracted_slots = complaint_collector.extract_slots(
        user_speech,
        current_field=current_field,
        existing_fields=session.get("fields", {})
    )
    for k, v in extracted_slots.items():
        if v and str(v).strip():
            # If a field is already collected, do not overwrite it with unprompted background extractions
            if session["fields"].get(k) and current_field != k and session.get("state") != "COLLECTING_EDIT":
                continue
            session["fields"][k] = v

    # If citizen details given without phone, attach caller_phone
    if session["fields"].get("citizen_details") and caller_phone:
        curr_val = session["fields"]["citizen_details"]
        if not re.search(r'\d{10}', curr_val):
            session["fields"]["citizen_details"] = f"{curr_val} ({caller_phone})"

    # Location GIS lookup
    loc_parts = [
        session["fields"].get("exact_location") or "",
        session["fields"].get("street_road_name") or "",
        session["fields"].get("district_area") or "",
        session["fields"].get("landmark") or ""
    ]
    loc_str = ", ".join([c for c in loc_parts if c]).strip()
    extract_location(loc_str or user_speech)

    # --- Check next missing field ---
    next_missing = complaint_collector.get_next_missing_field(session)

    if not next_missing:
        # All 10 fields collected -> confirmation summary
        session["state"] = "CONFIRMATION_PENDING"
        session["current_field_prompted"] = None
        summary_text, spoken_summary = complaint_collector.generate_summary(session, detected_lang)

        session["dialogue_turn"] = dialogue_turn + 1
        return VoiceRegisterTurnResponse(
            session_id=call_sid,
            call_sid=call_sid,
            dialogue_turn=dialogue_turn + 1,
            ai_reply=spoken_summary,
            ai_reply_tamil=summary_text if detected_lang == "Tamil" else spoken_summary,
            ai_reply_english=spoken_summary if detected_lang == "English" else summary_text,
            detected_language=detected_lang,
            language_confidence=lang_conf,
            intent="CONFIRMATION_PENDING",
            fields_collected=_count_collected(session),
            fields_total=FIELD_KEYS_COUNT,
            is_confirmation_pending=True,
            is_completed=False,
            collection_state=session["fields"]
        )

    # --- Still missing fields -> contextual question ---
    session["state"] = "COLLECTING"
    session["current_field_prompted"] = next_missing

    question_text, spoken_text = complaint_collector.get_contextual_question(session, next_missing, detected_lang)

    # Detect vague location input and add prefix
    if current_field in ["district_area", "street_road_name", "exact_location"] and complaint_collector.is_vague_location(user_speech):
        if detected_lang == "Tamil":
            spoken_text = f"\u0ba8\u0bc0\u0b99\u0bcd\u0b95\u0bb3\u0bcd \u0b95\u0bc2\u0bb1\u0bbf\u0baf \u0b87\u0b9f\u0bae\u0bcd \u0baa\u0bcb\u0ba4\u0bc1\u0bae\u0bbe\u0ba9\u0ba4\u0bbe\u0b95 \u0b87\u0bb2\u0bcd\u0bb2\u0bc8. {spoken_text}"
        elif detected_lang == "Tanglish":
            spoken_text = f"Neenga sonna location clear ah illa. {spoken_text}"
        else:
            spoken_text = f"The location provided is unclear. {spoken_text}"

    q_ta, _ = complaint_collector.get_contextual_question(session, next_missing, "Tamil")
    q_en, _ = complaint_collector.get_contextual_question(session, next_missing, "English")

    session["dialogue_turn"] = dialogue_turn + 1
    return VoiceRegisterTurnResponse(
        session_id=call_sid,
        call_sid=call_sid,
        dialogue_turn=dialogue_turn + 1,
        ai_reply=spoken_text,
        ai_reply_tamil=q_ta,
        ai_reply_english=q_en,
        detected_language=detected_lang,
        language_confidence=lang_conf,
        intent="GATHER_MORE_INFO",
        fields_collected=_count_collected(session),
        fields_total=FIELD_KEYS_COUNT,
        next_field=next_missing,
        is_confirmation_pending=False,
        is_completed=False,
        collection_state=session["fields"]
    )


# -----------------------------------------------------------------------------
# Route Handlers
# -----------------------------------------------------------------------------

@router.post("/voice-register/start", response_model=VoiceRegisterStartResponse)
def start_voice_register_session(req: VoiceRegisterStartRequest):
    """
    Start a new voice complaint registration session.
    Returns session_id, bilingual greeting, and first question.
    Called when citizen dials the Exotel toll-free number or opens the web simulator.
    """
    call_sid = req.exotel_call_sid or f"VR_{uuid.uuid4().hex[:16]}"

    lang_hint = req.language_hint if req.language_hint and req.language_hint != "Auto" else None
    session = complaint_collector.get_or_create_session(call_sid, language_hint=lang_hint)

    session["caller_phone"] = req.caller_phone
    session["language_preference"] = req.language_hint or "Auto"
    session["dialogue_turn"] = 1

    lang = lang_hint or "Tamil"
    greeting_ta, greeting_en, first_q = _build_greeting(lang)

    logger.info(f"[VoiceRegister] Session started: {call_sid} | Phone: {req.caller_phone} | Lang: {lang}")

    return VoiceRegisterStartResponse(
        session_id=call_sid,
        call_sid=call_sid,
        greeting_text=greeting_ta if lang == "Tamil" else (greeting_en if lang == "English" else greeting_ta),
        greeting_text_tamil=greeting_ta,
        greeting_text_english=greeting_en,
        detected_language=lang,
        first_question=first_q
    )


@router.post("/voice-register/turn", response_model=VoiceRegisterTurnResponse)
def voice_register_dialogue_turn(req: VoiceRegisterTurnRequest, db: Session = Depends(get_db)):
    """
    Submit one dialogue turn (citizen speech as text).
    Handles slot extraction, confirmation, registration, and Twilio SMS dispatch.
    """
    sid = req.session_id or req.call_sid or f"VR_{uuid.uuid4().hex[:12]}"
    session = complaint_collector.get_or_create_session(sid)
    if req.language_preference and req.language_preference != "Auto":
        session["language_preference"] = req.language_preference

    caller_phone = req.caller_phone or session.get("caller_phone", "+919843098765")

    return _process_dialogue_turn(
        session=session,
        user_speech=(req.user_speech or "").strip(),
        caller_phone=caller_phone,
        db=db
    )


@router.post("/voice-register/audio-turn", response_model=VoiceRegisterTurnResponse)
async def voice_register_audio_turn(
    file: UploadFile = File(...),
    session_id: str = Form(...),
    caller_phone: Optional[str] = Form(default="+919843098765"),
    language_hint: Optional[str] = Form(default=None),
    db: Session = Depends(get_db)
):
    """
    Submit one dialogue turn as an audio file upload.
    Transcribes audio -> runs dialogue turn -> returns AI reply.
    """
    _, ext = validate_audio_file(file)
    unique_filename = f"vr_{session_id}_{uuid.uuid4().hex[:8]}{ext}"
    saved_path = os.path.join(settings.UPLOAD_DIR, unique_filename)

    async with aiofiles.open(saved_path, "wb") as out_file:
        content = await file.read(settings.MAX_UPLOAD_SIZE_BYTES + 1024)
        if len(content) > settings.MAX_UPLOAD_SIZE_BYTES:
            raise BadRequestException("Audio file exceeds maximum allowed size of 25MB")
        await out_file.write(content)

    # Import audio prediction service for transcription
    from app.ai.audio_prediction_service import audio_prediction_service
    audio_pred = audio_prediction_service.analyze_audio_file(saved_path, language_hint=language_hint)
    transcribed = audio_pred.get("transcription", "").strip()

    # Fallback transcription for demo/offline mode
    if not transcribed:
        lang_code = language_hint or "en"
        if lang_code == "ta":
            transcribed = "\u0b95\u0bbf\u0bb0\u0bbe\u0bae\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0b95\u0bc1\u0b9f\u0bbf\u0ba8\u0bc0\u0bb0\u0bcd \u0bb5\u0bb0\u0bb5\u0bbf\u0bb2\u0bcd\u0bb2\u0bc8"
        else:
            transcribed = "There is a water supply problem in my area"

    session = complaint_collector.get_or_create_session(session_id)
    if language_hint:
        session["language_preference"] = language_hint

    return _process_dialogue_turn(
        session=session,
        user_speech=transcribed,
        caller_phone=caller_phone or "+919843098765",
        db=db
    )


@router.get("/voice-register/session/{session_id}", response_model=VoiceRegisterSessionResponse)
def get_voice_register_session(session_id: str):
    """
    Returns the current state of a voice registration session.
    Useful for frontend polling to sync UI with AI conversation state.
    """
    from app.ai.complaint_collector import SESSION_STORE
    if session_id not in SESSION_STORE:
        raise BadRequestException(f"Session '{session_id}' not found. Start a new session at /voice-register/start")

    session = SESSION_STORE[session_id]
    fields = session.get("fields", {})
    collected = sum(1 for k in FIELD_KEYS if fields.get(k) and str(fields[k]).strip())

    return VoiceRegisterSessionResponse(
        session_id=session_id,
        call_sid=session_id,
        state=session.get("state", "COLLECTING"),
        language=session.get("language", "English"),
        dialogue_turn=session.get("dialogue_turn", 1),
        fields=fields,
        fields_collected=collected,
        fields_total=FIELD_KEYS_COUNT,
        complaint_number=session.get("created_complaint_number"),
        complaint_id=session.get("created_complaint_id")
    )


# -----------------------------------------------------------------------------
# Exotel Live Webhook - Conversational AI Dialogue
# -----------------------------------------------------------------------------

@router.post("/webhooks/exotel/voice/dialogue")
async def exotel_voice_dialogue_webhook(request: Request, db: Session = Depends(get_db)):
    """Exotel Passthru webhook triggered on dialogue turns."""
    try:
        payload = await request.json()
    except Exception:
        form = await request.form()
        payload = dict(form)

    call_sid = payload.get("CallSid", f"VR_{uuid.uuid4().hex[:16]}")
    from_number = payload.get("From", "+919843098765")
    speech_result = payload.get("SpeechResult", "").strip()

    logger.info(f"[Exotel Dialogue] CallSid={call_sid} | From={from_number} | Speech='{speech_result[:80]}'")

    # Get or create session for this call
    session = complaint_collector.get_or_create_session(call_sid)
    if not session["fields"].get("citizen_details"):
        session["fields"]["citizen_details"] = from_number
    session["caller_phone"] = from_number

    if not speech_result:
        lang = session.get("language", "Tamil")
        if lang == "Tamil":
            prompt = "\u0bae\u0ba9\u0bcd\u0ba9\u0bbf\u0b95\u0bcd\u0b95\u0bb5\u0bc1\u0bae\u0bcd. \u0ba4\u0baf\u0bb5\u0bc1\u0b9a\u0bc6\u0baf\u0bcd\u0ba4\u0bc1 \u0bae\u0bc0\u0ba3\u0bcd\u0b9f\u0bc1\u0bae\u0bcd \u0b95\u0bc2\u0bb1\u0bb5\u0bc1\u0bae\u0bcd."
        else:
            prompt = "Sorry, I did not catch that. Please repeat."
        return {"status": "ok", "prompt": prompt, "call_sid": call_sid}

    result = _process_dialogue_turn(
        session=session,
        user_speech=speech_result,
        caller_phone=from_number,
        db=db
    )

    return {
        "status": "ok",
        "call_sid": call_sid,
        "prompt": result.ai_reply,
        "prompt_tamil": result.ai_reply_tamil,
        "prompt_english": result.ai_reply_english,
        "detected_language": result.detected_language,
        "intent": result.intent,
        "is_confirmation_pending": result.is_confirmation_pending,
        "is_completed": result.is_completed,
        "complaint_number": result.complaint_number,
        "sms_sent": result.sms_sent,
        "sms_failure_reason": result.sms_failure_reason,
        "fields_collected": result.fields_collected,
        "fields_total": result.fields_total
    }


# -----------------------------------------------------------------------------
# VoxentraAI Natural Live Conversational Voice Endpoints
# -----------------------------------------------------------------------------

from pydantic import BaseModel, Field


class ConversationTurnRequest(BaseModel):
    session_id: Optional[str] = None
    user_speech: str = Field(..., description="Citizen voice transcription or typed input")
    caller_phone: Optional[str] = "+919843098765"


class ConversationTurnResponse(BaseModel):
    session_id: str
    state: str  # WAITING_FOR_USER | CONFIRMING | COMPLETED | ERROR
    ai_text: str
    ai_spoken: str
    detected_language: str
    context: Dict[str, Any]
    confirmation_required: bool
    conversation_complete: bool
    complaint_number: Optional[str] = None
    complaint_id: Optional[int] = None


@router.post("/conversation/turn", response_model=ConversationTurnResponse)
def conversation_dialogue_turn(req: ConversationTurnRequest, db: Session = Depends(get_db)):
    """
    Submits one turn of live conversational dialogue to ConversationService.
    Processes speech, dynamically detects language, updates context,
    and returns AI response with state transitions.
    """
    from app.ai.conversation_service import conversation_service
    sid = req.session_id or f"conv_{uuid.uuid4().hex[:12]}"
    result = conversation_service.process_turn(
        session_id=sid,
        user_speech=req.user_speech,
        db=db,
        caller_phone=req.caller_phone
    )
    return ConversationTurnResponse(**result)


@router.post("/conversation/audio-turn", response_model=ConversationTurnResponse)
async def conversation_audio_turn(
    file: UploadFile = File(...),
    session_id: Optional[str] = Form(default=None),
    caller_phone: Optional[str] = Form(default="+919843098765"),
    db: Session = Depends(get_db)
):
    """
    Submits an audio speech turn to the live conversational voice engine.
    Uses speech_service for STT, and conversation_service for the multi-turn logic.
    """
    from app.ai.conversation_service import conversation_service
    from app.ai.speech_service import speech_service
    sid = session_id or f"conv_{uuid.uuid4().hex[:12]}"

    _, ext = validate_audio_file(file)
    unique_filename = f"conv_audio_{sid}_{uuid.uuid4().hex[:8]}{ext}"
    saved_path = os.path.join(settings.UPLOAD_DIR, unique_filename)

    async with aiofiles.open(saved_path, "wb") as out_file:
        content = await file.read(settings.MAX_UPLOAD_SIZE_BYTES + 1024)
        if len(content) > settings.MAX_UPLOAD_SIZE_BYTES:
            raise BadRequestException("Audio file exceeds maximum allowed size of 25MB")
        await out_file.write(content)

    trans_res = speech_service.transcribe(saved_path)
    user_speech = trans_res.get("transcription", "").strip()

    if not user_speech:
        # Check if Whisper is unavailable
        avail = speech_service.check_availability()
        if not avail["available"]:
            user_speech = "Voice recognition is not configured. Please type your complaint."
        else:
            user_speech = "umm..."

    result = conversation_service.process_turn(
        session_id=sid,
        user_speech=user_speech,
        db=db,
        caller_phone=caller_phone
    )
    return ConversationTurnResponse(**result)


@router.get("/conversation/session/{session_id}")
def get_conversation_session_state(session_id: str):
    """Returns the structured ConversationContext for session_id."""
    from app.ai.conversation_service import conversation_service
    ctx = conversation_service.get_or_create_context(session_id)
    return {
        "session_id": ctx.session_id,
        "context": ctx.to_dict()
    }


# -----------------------------------------------------------------------------
# WebSocket Live Audio / Text Streaming Endpoint (Real-Time Architecture)
# -----------------------------------------------------------------------------

from fastapi import WebSocket, WebSocketDisconnect
import json


@router.websocket("/voice/session/{session_id}/stream")
async def voice_session_websocket_stream(websocket: WebSocket, session_id: str, db: Session = Depends(get_db)):
    """
    WebSocket endpoint for real-time bidirectional conversational streaming.
    Receives JSON messages: {"type": "SPEECH_TURN", "text": "..."} or {"type": "AUDIO_CHUNK", "data": "..."}
    Streams back: {"type": "STATE_CHANGE", "state": "...", "ai_text": "...", "ai_spoken": "..."}
    """
    await websocket.accept()
    from app.ai.conversation_service import conversation_service
    ctx = conversation_service.get_or_create_context(session_id)

    try:
        await websocket.send_json({
            "type": "SESSION_INIT",
            "session_id": session_id,
            "state": "WAITING_FOR_USER",
            "message": "Connected to VoxentraAI Live Voice Engine. You can speak now."
        })

        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            msg_type = msg.get("type", "SPEECH_TURN")

            if msg_type == "SPEECH_TURN":
                user_speech = msg.get("text", "")
                await websocket.send_json({"type": "STATE_CHANGE", "state": "PROCESSING"})

                res = conversation_service.process_turn(
                    session_id=session_id,
                    user_speech=user_speech,
                    db=db,
                    caller_phone=msg.get("caller_phone", "+919843098765")
                )

                await websocket.send_json({
                    "type": "TURN_RESULT",
                    **res
                })
            elif msg_type == "PING":
                await websocket.send_json({"type": "PONG"})

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for session {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error in session {session_id}: {e}")
        try:
            await websocket.send_json({"type": "ERROR", "error": str(e)})
        except Exception:
            pass

