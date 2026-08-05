"""Authenticated user preference endpoints."""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app import db
from app.services.user_preferences import get_or_create, reset, update

auth_preferences_bp = Blueprint("auth_preferences", __name__)


@auth_preferences_bp.route("/preferences", methods=["GET"])
@jwt_required()
def get_preferences():
    preferences = get_or_create(int(get_jwt_identity()))
    db.session.commit()
    return jsonify({"preferences": preferences.to_dict()}), 200


@auth_preferences_bp.route("/preferences", methods=["PUT"])
@jwt_required()
def update_preferences():
    preferences = get_or_create(int(get_jwt_identity()))
    try:
        update(preferences, request.get_json(silent=True) or {})
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    db.session.commit()
    return jsonify({"preferences": preferences.to_dict()}), 200


@auth_preferences_bp.route("/preferences/reset", methods=["POST"])
@jwt_required()
def reset_preferences():
    preferences = get_or_create(int(get_jwt_identity()))
    reset(preferences)
    db.session.commit()
    return jsonify({"preferences": preferences.to_dict()}), 200
