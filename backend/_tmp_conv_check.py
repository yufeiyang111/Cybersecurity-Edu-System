# -*- coding: utf-8 -*-
from app import create_app, db

app = create_app()
with app.app_context():
    from app.models.qa import QAConversation

    all_conv = QAConversation.query.order_by(QAConversation.updated_at.desc()).all()
    print("total conversations:", len(all_conv))
    for c in all_conv[:20]:
        print(
            "  id=%s title=%r updated=%s archived=%s user=%s"
            % (
                c.id,
                (c.title or "").encode("unicode_escape").decode(),
                c.updated_at,
                c.is_archived,
                c.user_id,
            )
        )
