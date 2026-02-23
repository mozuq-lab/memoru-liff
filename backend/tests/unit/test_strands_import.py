"""Strands Agents SDK インポートテスト.

TASK-0052: SDK が正常にインストールされ、インポート可能であることを確認する。
"""


def test_strands_agent_import():
    """Strands Agent を import できることを確認."""
    from strands import Agent
    assert Agent is not None


def test_strands_tools_import():
    """Strands Tools を import できることを確認."""
    try:
        from strands.tools import tool
        assert tool is not None
    except ImportError:
        # strands-agents-tools may have different import paths
        import strands_agents_tools
        assert strands_agents_tools is not None
