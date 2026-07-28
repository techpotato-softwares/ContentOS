from training.schema import (
    TenantTrainingSchema,
    BrandVisualSection,
    render_context_pack,
    resolve_ui_theme,
    is_white_label_complete,
)


def test_context_pack_headers():
    pack = render_context_pack(TenantTrainingSchema())
    assert "## Company" in pack
    assert "## Messaging" in pack
    assert "not a topic allowlist" in pack.lower() or "brand consistency" in pack.lower()


def test_white_label_incomplete_defaults_platform():
    brand = BrandVisualSection(ui_mode="white_label", primary_color="#111")
    assert not is_white_label_complete(brand)
    theme = resolve_ui_theme(TenantTrainingSchema(brand_visual=brand))
    assert theme["source"] == "platform"


def test_white_label_complete():
    brand = BrandVisualSection(
        ui_mode="white_label",
        logo_url="https://example.com/logo.png",
        primary_color="#0d9488",
        secondary_color="#134e4a",
        accent_color="#2dd4bf",
        app_display_name="Acme",
    )
    assert is_white_label_complete(brand)
    theme = resolve_ui_theme(TenantTrainingSchema(brand_visual=brand))
    assert theme["source"] == "tenant"
    assert theme["appDisplayName"] == "Acme"
