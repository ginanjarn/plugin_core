from locale import getlocale
from os import getpid
from pathlib import Path
from uuid import uuid4

import sublime
import sublime_plugin

from ..session import InitializeStatus
from ..uri import path_to_uri
from ..lsprotocol.client import Client, InitializeResult


class _InitializeCommand(sublime_plugin.TextCommand):

    client = None

    def run(self, edit: sublime.Edit):
        self.client.initialize(self.view)


DEFAULT_PARAMS = {
    "processId": getpid(),
    "clientInfo": {"name": "Sublime Text", "version": sublime.version()},
    "locale": getlocale()[0],
    "rootPath": "",
    "rootUri": "",
    "capabilities": {
        "workspace": {
            "applyEdit": False,
            "workspaceEdit": {
                "documentChanges": False,
                "resourceOperations": [],
                "failureHandling": "abort",
                "normalizesLineEndings": False,
                "changeAnnotationSupport": {"groupsOnLabel": False},
                "metadataSupport": False,
                "snippetEditSupport": False,
            },
            "didChangeConfiguration": {"dynamicRegistration": False},
            "didChangeWatchedFiles": {
                "dynamicRegistration": False,
                "relativePatternSupport": False,
            },
            "symbol": {
                "dynamicRegistration": False,
                "symbolKind": {
                    "valueSet": [
                        1,
                        2,
                        3,
                        4,
                        5,
                        6,
                        7,
                        8,
                        9,
                        10,
                        11,
                        12,
                        13,
                        14,
                        15,
                        16,
                        17,
                        18,
                        19,
                        20,
                        21,
                        22,
                        23,
                        24,
                        25,
                        26,
                    ]
                },
                "tagSupport": {"valueSet": [1]},
                "resolveSupport": {"properties": []},
            },
            "executeCommand": {"dynamicRegistration": False},
            "workspaceFolders": False,
            "configuration": False,
            "semanticTokens": {"refreshSupport": False},
            "codeLens": {"refreshSupport": False},
            "fileOperations": {
                "dynamicRegistration": False,
                "didCreate": False,
                "willCreate": False,
                "didRename": False,
                "willRename": False,
                "didDelete": False,
                "willDelete": False,
            },
            "inlineValue": {"refreshSupport": False},
            "inlayHint": {"refreshSupport": False},
            "diagnostics": {"refreshSupport": False},
            "foldingRange": {"refreshSupport": False},
            "textDocumentContent": {"dynamicRegistration": False},
        },
        "textDocument": {
            "synchronization": {
                "dynamicRegistration": False,
                "willSave": False,
                "willSaveWaitUntil": False,
                "didSave": False,
            },
            "filters": {"relativePatternSupport": False},
            "completion": {
                "dynamicRegistration": False,
                "completionItem": {
                    "snippetSupport": False,
                    "commitCharactersSupport": False,
                    "documentationFormat": [],
                    "deprecatedSupport": False,
                    "preselectSupport": False,
                    "tagSupport": {"valueSet": [1]},
                    "insertReplaceSupport": False,
                    "resolveSupport": {"properties": []},
                    "insertTextModeSupport": {"valueSet": [1, 2]},
                    "labelDetailsSupport": False,
                },
                "completionItemKind": {
                    "valueSet": [
                        1,
                        2,
                        3,
                        4,
                        5,
                        6,
                        7,
                        8,
                        9,
                        10,
                        11,
                        12,
                        13,
                        14,
                        15,
                        16,
                        17,
                        18,
                        19,
                        20,
                        21,
                        22,
                        23,
                        24,
                        25,
                    ]
                },
                "insertTextMode": 1,
                "contextSupport": False,
                "completionList": {"itemDefaults": [], "applyKindSupport": False},
            },
            "hover": {"dynamicRegistration": False, "contentFormat": []},
            "signatureHelp": {
                "dynamicRegistration": False,
                "signatureInformation": {
                    "documentationFormat": [],
                    "parameterInformation": {"labelOffsetSupport": False},
                    "activeParameterSupport": False,
                    "noActiveParameterSupport": False,
                },
                "contextSupport": False,
            },
            "declaration": {"dynamicRegistration": False, "linkSupport": False},
            "definition": {"dynamicRegistration": False, "linkSupport": False},
            "typeDefinition": {"dynamicRegistration": False, "linkSupport": False},
            "implementation": {"dynamicRegistration": False, "linkSupport": False},
            "references": {"dynamicRegistration": False},
            "documentHighlight": {"dynamicRegistration": False},
            "documentSymbol": {
                "dynamicRegistration": False,
                "symbolKind": {
                    "valueSet": [
                        1,
                        2,
                        3,
                        4,
                        5,
                        6,
                        7,
                        8,
                        9,
                        10,
                        11,
                        12,
                        13,
                        14,
                        15,
                        16,
                        17,
                        18,
                        19,
                        20,
                        21,
                        22,
                        23,
                        24,
                        25,
                        26,
                    ]
                },
                "hierarchicalDocumentSymbolSupport": False,
                "tagSupport": {"valueSet": [1]},
                "labelSupport": False,
            },
            "codeAction": {
                "dynamicRegistration": False,
                "codeActionLiteralSupport": {
                    "codeActionKind": {
                        "valueSet": [
                            "",
                            "quickfix",
                            "refactor",
                            "refactor.extract",
                            "refactor.inline",
                            "refactor.move",
                            "refactor.rewrite",
                            "source",
                            "source.organizeImports",
                            "source.fixAll",
                            "notebook",
                        ]
                    }
                },
                "isPreferredSupport": False,
                "disabledSupport": False,
                "dataSupport": False,
                "resolveSupport": {"properties": []},
                "honorsChangeAnnotations": False,
                "documentationSupport": False,
                "tagSupport": {"valueSet": [1]},
            },
            "codeLens": {
                "dynamicRegistration": False,
                "resolveSupport": {"properties": []},
            },
            "documentLink": {"dynamicRegistration": False, "tooltipSupport": False},
            "colorProvider": {"dynamicRegistration": False},
            "formatting": {"dynamicRegistration": False},
            "rangeFormatting": {"dynamicRegistration": False, "rangesSupport": False},
            "onTypeFormatting": {"dynamicRegistration": False},
            "rename": {
                "dynamicRegistration": False,
                "prepareSupport": False,
                "prepareSupportDefaultBehavior": 1,
                "honorsChangeAnnotations": False,
            },
            "foldingRange": {
                "dynamicRegistration": False,
                "rangeLimit": 0,
                "lineFoldingOnly": False,
                "foldingRangeKind": {"valueSet": ["comment", "imports", "region"]},
                "foldingRange": {"collapsedText": False},
            },
            "selectionRange": {"dynamicRegistration": False},
            "publishDiagnostics": {
                "relatedInformation": False,
                "tagSupport": {"valueSet": [1, 2]},
                "codeDescriptionSupport": False,
                "dataSupport": False,
                "versionSupport": False,
            },
            "callHierarchy": {"dynamicRegistration": False},
            "semanticTokens": {
                "dynamicRegistration": False,
                "requests": {"range": False, "full": False},
                "tokenTypes": [],
                "tokenModifiers": [],
                "formats": [],
                "overlappingTokenSupport": False,
                "multilineTokenSupport": False,
                "serverCancelSupport": False,
                "augmentsSyntaxTokens": False,
            },
            "linkedEditingRange": {"dynamicRegistration": False},
            "moniker": {"dynamicRegistration": False},
            "typeHierarchy": {"dynamicRegistration": False},
            "inlineValue": {"dynamicRegistration": False},
            "inlayHint": {
                "dynamicRegistration": False,
                "resolveSupport": {"properties": []},
            },
            "diagnostic": {
                "relatedInformation": False,
                "tagSupport": {"valueSet": [1, 2]},
                "codeDescriptionSupport": False,
                "dataSupport": False,
                "dynamicRegistration": False,
                "relatedDocumentSupport": False,
            },
            "inlineCompletion": {"dynamicRegistration": False},
        },
        "notebookDocument": {
            "synchronization": {
                "dynamicRegistration": False,
                "executionSummarySupport": False,
            }
        },
        "window": {
            "workDoneProgress": False,
            "showMessage": {
                "messageActionItem": {"additionalPropertiesSupport": False}
            },
            "showDocument": {"support": False},
        },
        "general": {
            "staleRequestSupport": {"cancel": False, "retryOnContentModified": []},
            "regularExpressions": {"engine": "", "version": ""},
            "markdown": {"parser": "", "version": "", "allowedTags": []},
            "positionEncodings": [],
        },
        "experimental": {},
    },
    "initializationOptions": {},
    "trace": "off",
    "workDoneToken": int(uuid4()),
    "workspaceFolders": [],
}


class InitializerMixins(Client):

    def initialize(self, view: sublime.View):
        # cancel if initializing
        if self.session.initialize_status is InitializeStatus.Initializing:
            return
        self.session.initialize_status = InitializeStatus.Initializing

        # check if view not closed
        if view is None:
            return

        workspace_path = get_workspace_path(view)
        if not workspace_path:
            return
        self.session.workspace_path = workspace_path

        params = DEFAULT_PARAMS.copy()
        params["rootPath"] = workspace_path
        params["rootUri"] = path_to_uri(workspace_path)
        params["trace"] = "on"

        params["capabilities"]["workspace"]["applyEdit"] = True
        params["capabilities"]["workspace"]["workspaceEdit"]["documentChanges"] = True
        params["capabilities"]["workspace"]["fileOperations"]["didCreate"] = True
        params["capabilities"]["workspace"]["fileOperations"]["didRename"] = True
        params["capabilities"]["workspace"]["fileOperations"]["didDelete"] = True

        params["capabilities"]["textDocument"]["synchronization"]["didSave"] = True
        params["capabilities"]["textDocument"]["completion"]["completionItem"][
            "snippetSupport"
        ] = True
        params["capabilities"]["textDocument"]["completion"]["completionItem"][
            "labelDetailsSupport"
        ] = True
        params["capabilities"]["textDocument"]["rename"]["prepareSupport"] = True

        self.session.client_capabilities = params["capabilities"]
        self.initialize_request(params)

    def handle_initialize_result(self, context: dict, result: InitializeResult) -> None:
        self.session.server_capabilities = result["capabilities"]
        self.initialized()

    def initialized(self):
        self.initialized_notification({})
        self.session.initialize_status = InitializeStatus.Initialized


def get_workspace_path(view: sublime.View, return_parent: bool = True) -> str:
    """Get workspace path for view.

    Params:
        view: View
            target
        return_parent: bool
            if True, return parent folder if view not opened in 'Window folders'

    Returns:
        workspace path or empty string
    """
    file_name = view.file_name()
    if not file_name:
        return ""

    if folders := [
        folder for folder in view.window().folders() if file_name.startswith(folder)
    ]:
        # File is opened in multiple folder
        return max(folders)

    if not return_parent:
        return ""

    return str(Path(file_name).parent)
