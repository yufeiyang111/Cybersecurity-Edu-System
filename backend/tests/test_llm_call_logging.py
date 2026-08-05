from app import db
from app.models.llm import LLMCallLog
from app.models.user import User
from app.services.llm.call_logging import observe_provider
from app.services.llm.contracts import LLMRequest, LLMResponse, LLMStreamChunk


class _Provider:
    provider_name = "private"
    model = "private-model"
    provider_config_id = 7

    def generate(self, request):
        return LLMResponse(
            text="safe answer",
            provider_name=self.provider_name,
            model=self.model,
            status_code=200,
            usage={"prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 14},
        )


class _StreamProvider(_Provider):
    def generate_stream(self, request):
        yield LLMStreamChunk(delta="safe answer")
        yield LLMStreamChunk(finished=True)


def _user():
    user = User(username="logging-user", email="logging@example.test", password_hash="x")
    db.session.add(user)
    db.session.flush()
    return user


def test_observed_non_stream_call_records_only_usage_metadata(app):
    with app.app_context():
        user = _user()
        observed = observe_provider(_Provider(), user_id=user.id, operation="qa")

        response = observed.generate(LLMRequest(prompt="prompt must not be stored"))

        assert response.is_success
        log = LLMCallLog.query.filter_by(user_id=user.id).one()
        assert log.status == "success"
        assert log.total_tokens == 14
        assert log.input_tokens == 10
        assert log.output_tokens == 4
        assert log.operation == "qa"
        assert log.provider_config_id == 7
        assert "prompt must not be stored" not in repr(log.to_dict())


def test_observed_stream_call_records_success_with_estimated_output(app):
    with app.app_context():
        user = _user()
        observed = observe_provider(_StreamProvider(), user_id=user.id, operation="suggestion")

        chunks = list(observed.generate_stream(LLMRequest(prompt="safe prompt")))

        assert chunks[-1].finished is True
        log = LLMCallLog.query.filter_by(user_id=user.id).one()
        assert log.status == "success"
        assert log.streaming is True
        assert log.output_tokens > 0
