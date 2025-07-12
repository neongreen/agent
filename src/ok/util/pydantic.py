import argparse
import inspect
import json
import re
from textwrap import dedent
from typing import Any, override

import pydantic.fields
import pydantic_settings


class _CliYesNoFlag:
    """Marker for CLI boolean flags to generate --foo and --no-foo options."""

    pass


class _CliBooleanFlag:
    """Marker for CLI boolean flags to expect --foo=True and --foo=False options."""

    pass


class _CliHideDefault:
    """Marker for CLI fields to hide the default value in the help text."""

    pass


class CliSettingsSource(pydantic_settings.CliSettingsSource):
    """Custom CLI settings source patching some of the Pydantic behavior"""

    @override
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Check if we are patching what we expect
        if not hasattr(super(), "_convert_bool_flag"):
            raise RuntimeError("Trying to patch _convert_bool_flag method in CliSettingsSource but it was not found.")
        else:
            source = dedent(inspect.getsource(super()._convert_bool_flag)).strip()
            expected_source = dedent("""
                def _convert_bool_flag(self, kwargs: dict[str, Any], field_info: FieldInfo, model_default: Any) -> None:
                    if kwargs['metavar'] == 'bool':
                        if (self.cli_implicit_flags or _CliImplicitFlag in field_info.metadata) and (
                            _CliExplicitFlag not in field_info.metadata
                        ):
                            del kwargs['metavar']
                            kwargs['action'] = BooleanOptionalAction
                """).strip()
            if source != expected_source:
                raise RuntimeError(
                    "The _convert_bool_flag method in CliSettingsSource has been changed.\n"
                    "Please update the patch accordingly.\n"
                    f"Expected:\n\n{expected_source}\n\nGot:\n\n{source}"
                )

    @override
    def _convert_bool_flag(
        self, kwargs: dict[str, Any], field_info: pydantic.fields.FieldInfo, model_default: Any
    ) -> None:
        """
        Overridden version of _convert_bool_flag that accepts _CliYesNoFlag and _CliBooleanFlag markers.
        Otherwise the default is "store_true".
        """

        if kwargs["metavar"] == "bool":
            if _CliYesNoFlag in field_info.metadata:
                del kwargs["metavar"]
                kwargs["action"] = argparse.BooleanOptionalAction
            elif _CliBooleanFlag in field_info.metadata:
                pass
            else:
                if field_info.default is True:
                    raise ValueError(
                        f"Cannot use --{field_info.validation_alias} as an enable-only CLI flag since it defaults to True.\n"
                        "Use _CliBooleanFlag or _CliYesNoFlag instead."
                    )
                del kwargs["metavar"]
                kwargs["action"] = "store_true"

    @override
    def _help_format(
        self, field_name: str, field_info: pydantic.fields.FieldInfo, model_default: Any, is_model_suppressed: bool
    ) -> str:
        """
        Custom help formatting to remove default values for fields marked with _CliHideDefault.
        """

        help_text = super()._help_format(field_name, field_info, model_default, is_model_suppressed)
        if _CliHideDefault in field_info.metadata or (
            field_info.default is False
            and not (_CliBooleanFlag in field_info.metadata or _CliYesNoFlag in field_info.metadata)
        ):
            help_text = re.sub(r" \(default: [^()]*\)$", "", help_text)
        return help_text

    @override
    def _merge_parsed_list(self, parsed_list: list[str], field_name: str) -> str:
        """
        Never try to parse lists. Whatever argparser gives us, that's what we want.
        """
        return json.dumps(parsed_list)


def with_metadata(field: Any, *args: Any) -> Any:
    """
    Helper function to create a FieldInfo with metadata.
    """

    if not isinstance(field, pydantic.fields.FieldInfo):
        raise TypeError("Expected a pydantic FieldInfo instance.")
    field.metadata = [*field.metadata, *args]
    return field
