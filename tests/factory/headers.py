import factory
from factory import DictFactory


class HeadersFactory(DictFactory):
    account = "aqa"
    role = "owner"
    user = "aqaEx@example.com"

    @classmethod
    def _build(cls, model_class, *args, **kwargs):
        data = super()._build(model_class, *args, **kwargs)
        headers = {
            "x-auth-account": data.get("account"),
            "x-auth-role":    data.get("role"),
            "x-auth-user":    data.get("user"),
            "Content-Type":   "application/json",
        }
        for k in ("account", "role", "user", "content_type"):
            data.pop(k, None)
        headers.update(data)

        return {k: v for k, v in headers.items() if v is not None}

    class Params:
        aqa = factory.Trait(account="aqa")
        aqa_owner = factory.Trait(account="aqa", role="owner")
        aqa_admin = factory.Trait(account="aqa", role="admin")
        aqa_member = factory.Trait(account="aqa", role="member")
        operator = factory.Trait(account="devel", role="operator", user="operator@example.com")
