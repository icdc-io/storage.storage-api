import factory
from factory import DictFactory


class HeadersPayload(DictFactory):
    """Factory for building HTTP headers for API authentication."""
    account: str  # must be passed explicitly
    role: str     # must be passed explicitly
    user = factory.Sequence(lambda n: f"test_email{n}@example.com")

    @classmethod
    def build(cls, **overrides) -> dict:
        data = super().build(**overrides)
        headers = {
            "x-auth-account": data.pop("account", None),
            "x-auth-role":    data.pop("role", None),
            "x-auth-user":    data.pop("user", None),
            "Content-Type":   "application/json",
        }
        headers.update(data)
        return {k: v for k, v in headers.items() if v is not None}

    class Params:
        aqa_owner  = factory.Trait(account="aqa", role="owner")
        aqa_admin  = factory.Trait(account="aqa", role="admin")
        aqa_member = factory.Trait(account="aqa", role="member")
        operator   = factory.Trait(account="devel", role="operator")
