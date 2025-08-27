from sqlalchemy.orm import declarative_base, relationship, Mapped, mapped_column
from sqlalchemy import Integer, String, Text, JSON, ForeignKey, DateTime, func
from passlib.hash import bcrypt

Base = declarative_base()

class Tenant(Base):
    __tablename__ = "tenants"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    created_at: Mapped[int] = mapped_column(Integer, server_default=func.strftime("%s","now"))

class Agent(Base):
    __tablename__ = "agents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"))
    agent_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    api_key_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[int] = mapped_column(Integer, server_default=func.strftime("%s","now"))
    tenant = relationship("Tenant", backref="agents")

    def set_api_key(self, raw: str):
        self.api_key_hash = bcrypt.hash(raw)

    def verify_api_key(self, raw: str) -> bool:
        return bcrypt.verify(raw, self.api_key_hash)

class Policy(Base):
    __tablename__ = "policies"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"))
    yaml: Mapped[str] = mapped_column(Text, nullable=False)
    json_bundle: Mapped[dict] = mapped_column(JSON, nullable=False)
    signature: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[int] = mapped_column(Integer, server_default=func.strftime("%s","now"))
    agent = relationship("Agent", backref="policies")

class Approval(Base):
    __tablename__ = "approvals"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"))
    tool: Mapped[str] = mapped_column(String(255))
    params_hash: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending|approved|denied
    payload_redacted: Mapped[dict|None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[int] = mapped_column(Integer, server_default=func.strftime("%s","now"))
    agent = relationship("Agent", backref="approvals")

class ToolCall(Base):
    __tablename__ = "tool_calls"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agent_id: Mapped[int|None] = mapped_column(ForeignKey("agents.id"), nullable=True)
    timestamp: Mapped[str] = mapped_column(String(32), nullable=False)
    tool: Mapped[str] = mapped_column(String(255), nullable=False)
    arguments: Mapped[dict] = mapped_column(JSON, nullable=False)
    result: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)  # approved|denied
    source: Mapped[str] = mapped_column(String(64), nullable=False)  # mcp-server, sdk, etc
    created_at: Mapped[int] = mapped_column(Integer, server_default=func.strftime("%s","now"))
    agent = relationship("Agent", backref="tool_calls")