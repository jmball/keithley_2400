"""Optional Series 2400 capabilities used to skip unsupported hardware tests."""

# Optional capabilities that some Series 2400 instruments lack. Tests that use one
# are marked @pytest.mark.requires("<feature>") and skip when it is unsupported.
FEATURES = {
    # The 2401 has no digital output lines or component handler interface.
    "digital_output": lambda model, options: model != "2401",
    # The pulse source function exists only on the 2430.
    "pulse": lambda model, options: model == "2430",
    # *OPT? reports CONTACT-CHECK when the contact-check option is installed.
    "contact_check": lambda model, options: any(
        "CONTACT" in option for option in options
    ),
}


def supported_features(identity: str, options: tuple[str, ...]) -> set[str]:
    """Return the optional features implied by *IDN? identity and *OPT? options."""
    model = identity.split(",")[1].strip().removeprefix("MODEL ")
    return {name for name, check in FEATURES.items() if check(model, options)}
