"""사진 캡션과 사진 엔티티 채택 규칙. 외부 호출 없이 검증한다."""


from silen_worker.photo.caption import (
    CAPTION_MAX,
    anchored_entities,
    caption_guardrail,
    embeddable_text,
)
from silen_worker.extraction.service import ExtractedEntity


class TestCaption:
    def test_빈_캡션은_버린다(self):
        assert caption_guardrail("") is None
        assert caption_guardrail("   ") is None

    def test_너무_길면_버린다(self):
        assert caption_guardrail("가" * (CAPTION_MAX + 1)) is None

    def test_정상_캡션은_통과한다(self):
        assert caption_guardrail(" 컵, 창문 ") == "컵, 창문"

    def test_추측_표현은_버린다(self):
        """캡션은 보이는 것만 적는다. '~인 듯', '~같다'는 추측이다."""
        assert caption_guardrail("카페인 것 같다") is None
        assert caption_guardrail("행복해 보인다") is None


class TestEmbeddableText:
    def test_글과_캡션을_합친다(self):
        assert embeddable_text("라떼 마셨다", "컵, 창문") == "라떼 마셨다\n컵, 창문"

    def test_사진만_있으면_캡션만_쓴다(self):
        """글이 없는 기록은 지금까지 임베딩조차 되지 않아 검색에서 사라졌다."""
        assert embeddable_text(None, "컵, 창문") == "컵, 창문"

    def test_캡션이_없으면_글만_쓴다(self):
        assert embeddable_text("라떼 마셨다", None) == "라떼 마셨다"

    def test_둘_다_없으면_없다(self):
        assert embeddable_text(None, None) is None


class TestAnchor:
    """사진 엔티티에는 원문 대조 앵커가 없다. 사용자 언어를 앵커로 삼는다."""

    def _e(self, name: str) -> ExtractedEntity:
        return ExtractedEntity(type="thing", name=name, normalized_name=name)

    def test_사용자가_쓴_적_있는_말만_채택한다(self):
        found = anchored_entities(
            [self._e("카페"), self._e("창문")],
            user_vocabulary={"카페", "라떼"},
        )
        assert [e.name for e in found] == ["카페"]

    def test_사용자_어휘가_비면_아무것도_채택하지_않는다(self):
        assert anchored_entities([self._e("카페")], user_vocabulary=set()) == []

    def test_불용어는_어휘에_있어도_버린다(self):
        assert anchored_entities(
            [self._e("점심")], user_vocabulary={"점심"}
        ) == []
