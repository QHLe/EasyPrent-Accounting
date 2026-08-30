from __future__ import annotations


def build_object_lifecycle_paths() -> dict:
    objects = {
        "properties": ("Anlage", "eine", "eine archivierte"),
        "buildings": ("Gebäude", "ein", "ein archiviertes"),
        "units": ("Wohnung", "eine", "eine archivierte"),
        "rooms": ("Zimmer", "ein", "ein archiviertes"),
        "meters": ("Zähler", "einen", "einen archivierten"),
        "expenses": ("Kostenposition", "eine", "eine archivierte"),
    }
    paths: dict = {}
    for resource_name, config in objects.items():
        label, archive_article, delete_article = config
        paths[f"/api/{resource_name}/{{id}}/archive"] = {
            "post": {
                "summary": f"Archiviert {archive_article} {label}",
                "parameters": [
                    {
                        "name": "id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "integer"},
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Archiviertes Objekt",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ObjectArchiveResponse"}
                            }
                        },
                    },
                    "400": {
                        "description": "Ungültige Archivierungsanfrage",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                            }
                        },
                    },
                },
            }
        }
        paths[f"/api/{resource_name}/{{id}}/restore"] = {
            "post": {
                "summary": f"Hebt die Archivierung für {label} auf",
                "parameters": [
                    {
                        "name": "id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "integer"},
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Wiederhergestelltes Objekt",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ObjectArchiveResponse"}
                            }
                        },
                    },
                    "400": {
                        "description": "Ungültige Wiederherstellungsanfrage",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                            }
                        },
                    },
                },
            }
        }
        paths[f"/api/{resource_name}/{{id}}"] = {
            "delete": {
                "summary": f"Löscht {delete_article} {label}",
                "parameters": [
                    {
                        "name": "id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "integer"},
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Gelöschtes Objekt",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ObjectDeleteResponse"}
                            }
                        },
                    },
                    "400": {
                        "description": "Ungültige Löschanfrage",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                            }
                        },
                    },
                },
            }
        }
    return paths


def build_openapi_document() -> dict:
    return {
        "openapi": "3.1.0",
        "info": {
            "title": "EasyPrent Accounting API",
            "version": "0.1.0",
            "description": (
                "HTTP-Schnittstelle für Immobilien, Mietverträge, Nebenkosten und "
                "Abschreibungen im EasyPrent-Accounting-MVP."
            ),
        },
        "servers": [{"url": "/"}],
        "paths": {
            "/api/properties": {
                "post": {
                    "summary": "Erstellt eine neue Anlage oder Immobilie",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/PropertyCreateRequest"}
                            }
                        },
                    },
                    "responses": {
                        "201": {
                            "description": "Erstellte Anlage",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/PropertyResponse"}
                                }
                            },
                        }
                    },
                }
            },
            "/api/buildings": {
                "post": {
                    "summary": "Erstellt ein Gebäude",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/BuildingCreateRequest"}
                            }
                        },
                    },
                    "responses": {
                        "201": {
                            "description": "Erstelltes Gebäude",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/BuildingResponse"}
                                }
                            },
                        }
                    },
                }
            },
            "/api/units": {
                "post": {
                    "summary": "Erstellt eine Wohnung",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/UnitCreateRequest"}
                            }
                        },
                    },
                    "responses": {
                        "201": {
                            "description": "Erstellte Wohnung",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/UnitResponse"}
                                }
                            },
                        }
                    },
                }
            },
            "/api/rooms": {
                "post": {
                    "summary": "Erstellt ein Zimmer für eine Wohnung",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/RoomCreateRequest"}
                            }
                        },
                    },
                    "responses": {
                        "201": {
                            "description": "Erstelltes Zimmer",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/RoomResponse"}
                                }
                            },
                        }
                    },
                }
            },
            "/api/tenants": {
                "post": {
                    "summary": "Erstellt einen Mieter",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/TenantCreateRequest"}
                            }
                        },
                    },
                    "responses": {
                        "201": {
                            "description": "Erstellter Mieter",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/TenantResponse"}
                                }
                            },
                        }
                    },
                }
            },
            "/api/leases": {
                "post": {
                    "summary": "Erstellt einen Mietvertrag",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/LeaseCreateRequest"}
                            }
                        },
                    },
                    "responses": {
                        "201": {
                            "description": "Erstellter Mietvertrag",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/LeaseResponse"}
                                }
                            },
                        }
                    },
                }
            },
            "/api/tenants/{id}/documents": {
                "get": {
                    "summary": "Listet Dokumente eines Mieters",
                    "parameters": [
                        {
                            "name": "id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer"},
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Dokumentliste",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/LinkedDocumentListResponse"
                                    }
                                }
                            },
                        },
                        "400": {
                            "description": "Ungültige Anfrage",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                                }
                            },
                        },
                    },
                },
                "post": {
                    "summary": "Lädt ein oder mehrere Dokumente für einen Mieter hoch",
                    "parameters": [
                        {
                            "name": "id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer"},
                        }
                    ],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/LinkedDocumentUploadRequest"
                                }
                            }
                        },
                    },
                    "responses": {
                        "201": {
                            "description": "Hochgeladene Dokumente",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/LinkedDocumentListResponse"
                                    }
                                }
                            },
                        },
                        "400": {
                            "description": "Ungültige Eingabedaten",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                                }
                            },
                        },
                    },
                },
            },
            "/api/tenants/{id}/documents/{document_id}": {
                "delete": {
                    "summary": "Löscht ein Dokument eines Mieters",
                    "parameters": [
                        {
                            "name": "id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer"},
                        },
                        {
                            "name": "document_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer"},
                        },
                    ],
                    "responses": {
                        "200": {
                            "description": "Gelöschtes Dokument",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/LinkedDocumentDeleteResponse"
                                    }
                                }
                            },
                        },
                        "400": {
                            "description": "Ungültige Löschanfrage",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                                }
                            },
                        },
                    },
                }
            },
            "/api/tenants/{id}/documents/{document_id}/download": {
                "get": {
                    "summary": "Lädt ein Dokument eines Mieters herunter",
                    "parameters": [
                        {
                            "name": "id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer"},
                        },
                        {
                            "name": "document_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer"},
                        },
                    ],
                    "responses": {
                        "200": {
                            "description": "Dateiinhalt",
                            "content": {
                                "application/octet-stream": {
                                    "schema": {"type": "string", "format": "binary"}
                                }
                            },
                        },
                        "400": {
                            "description": "Ungültige Anfrage",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                                }
                            },
                        },
                    },
                }
            },
            "/api/leases/{id}/documents": {
                "get": {
                    "summary": "Listet Dokumente eines Mietvertrags",
                    "parameters": [
                        {
                            "name": "id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer"},
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Dokumentliste",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/LinkedDocumentListResponse"
                                    }
                                }
                            },
                        },
                        "400": {
                            "description": "Ungültige Anfrage",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                                }
                            },
                        },
                    },
                },
                "post": {
                    "summary": "Lädt ein oder mehrere Dokumente für einen Mietvertrag hoch",
                    "parameters": [
                        {
                            "name": "id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer"},
                        }
                    ],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/LinkedDocumentUploadRequest"
                                }
                            }
                        },
                    },
                    "responses": {
                        "201": {
                            "description": "Hochgeladene Dokumente",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/LinkedDocumentListResponse"
                                    }
                                }
                            },
                        },
                        "400": {
                            "description": "Ungültige Eingabedaten",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                                }
                            },
                        },
                    },
                },
            },
            "/api/leases/{id}/documents/{document_id}": {
                "delete": {
                    "summary": "Löscht ein Dokument eines Mietvertrags",
                    "parameters": [
                        {
                            "name": "id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer"},
                        },
                        {
                            "name": "document_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer"},
                        },
                    ],
                    "responses": {
                        "200": {
                            "description": "Gelöschtes Dokument",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/LinkedDocumentDeleteResponse"
                                    }
                                }
                            },
                        },
                        "400": {
                            "description": "Ungültige Löschanfrage",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                                }
                            },
                        },
                    },
                }
            },
            "/api/leases/{id}/documents/{document_id}/download": {
                "get": {
                    "summary": "Lädt ein Dokument eines Mietvertrags herunter",
                    "parameters": [
                        {
                            "name": "id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer"},
                        },
                        {
                            "name": "document_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer"},
                        },
                    ],
                    "responses": {
                        "200": {
                            "description": "Dateiinhalt",
                            "content": {
                                "application/octet-stream": {
                                    "schema": {"type": "string", "format": "binary"}
                                }
                            },
                        },
                        "400": {
                            "description": "Ungültige Anfrage",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                                }
                            },
                        },
                    },
                }
            },
            "/api/overview": {
                "get": {
                    "summary": "Lädt die Übersicht für Dashboard und React-Oberfläche",
                    "responses": {
                        "200": {
                            "description": "Übersichtsdaten",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/OverviewResponse"}
                                }
                            },
                        }
                    },
                }
            },
            "/api/health": {
                "get": {
                    "summary": "Prüft die Erreichbarkeit des Servers",
                    "responses": {
                        "200": {
                            "description": "Serverstatus",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/HealthResponse"}
                                }
                            },
                        }
                    },
                }
            },
            "/api/paperless-status": {
                "get": {
                    "summary": "Prüft die Erreichbarkeit des konfigurierten Paperless-Servers",
                    "responses": {
                        "200": {
                            "description": "Paperless-Verbindungsstatus",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/PaperlessStatusResponse"
                                    }
                                }
                            },
                        }
                    },
                }
            },
            "/api/paperless-settings": {
                "get": {
                    "summary": "Lädt die gespeicherten Paperless-Einstellungen",
                    "responses": {
                        "200": {
                            "description": "Paperless-Einstellungen",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/PaperlessSettingsResponse"
                                    }
                                }
                            },
                        }
                    },
                },
                "put": {
                    "summary": "Speichert Paperless-URL und API-Token",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/PaperlessSettingsUpdateRequest"
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Aktualisierte Paperless-Einstellungen",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/PaperlessSettingsResponse"
                                    }
                                }
                            },
                        },
                        "400": {
                            "description": "Ungültige Eingabedaten",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                                }
                            },
                        },
                    },
                },
            },
            "/api/application-settings": {
                "get": {
                    "summary": "Lädt allgemeine Anwendungseinstellungen",
                    "responses": {
                        "200": {
                            "description": "Anwendungseinstellungen",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/ApplicationSettingsResponse"
                                    }
                                }
                            },
                        }
                    },
                },
                "put": {
                    "summary": "Speichert allgemeine Anwendungseinstellungen",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/ApplicationSettingsUpdateRequest"
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Aktualisierte Anwendungseinstellungen",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/ApplicationSettingsResponse"
                                    }
                                }
                            },
                        },
                        "400": {
                            "description": "Ungültige Eingabedaten",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                                }
                            },
                        },
                    },
                },
            },
            "/api/application-export": {
                "get": {
                    "summary": "Exportiert den aktuellen Anwendungsdatenbestand",
                    "responses": {
                        "200": {
                            "description": "Exportierte Sicherungsdaten",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/ApplicationExportResponse"
                                    }
                                }
                            },
                        }
                    },
                }
            },
            "/api/application-import": {
                "post": {
                    "summary": "Importiert einen zuvor exportierten Anwendungsdatenbestand",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/ApplicationImportRequest"
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Importiertes Sicherungsergebnis",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/ApplicationImportResponse"
                                    }
                                }
                            },
                        },
                        "400": {
                            "description": "Ungültige Importdaten",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                                }
                            },
                        },
                    },
                }
            },
            "/api/settlements": {
                "get": {
                    "summary": "Berechnet eine Nebenkostenabrechnung für einen Zeitraum",
                    "parameters": [
                        {
                            "name": "property_id",
                            "in": "query",
                            "required": True,
                            "schema": {"type": "integer"},
                        },
                        {
                            "name": "period_start",
                            "in": "query",
                            "required": True,
                            "schema": {"type": "string", "format": "date"},
                        },
                        {
                            "name": "period_end",
                            "in": "query",
                            "required": True,
                            "schema": {"type": "string", "format": "date"},
                        },
                    ],
                    "responses": {
                        "200": {
                            "description": "Abrechnungsdaten",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/SettlementResponse"}
                                }
                            },
                        }
                    },
                }
            },
            "/api/depreciation-schedule": {
                "get": {
                    "summary": "Lädt den Abschreibungsplan eines Jahres",
                    "parameters": [
                        {
                            "name": "year",
                            "in": "query",
                            "required": True,
                            "schema": {"type": "integer"},
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Abschreibungsplan",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/DepreciationScheduleResponse"
                                    }
                                }
                            },
                        }
                    },
                }
            },
            "/api/expenses": {
                "post": {
                    "summary": "Erstellt eine neue Kostenposition",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ExpenseCreateRequest"}
                            }
                        },
                    },
                    "responses": {
                        "201": {
                            "description": "Erstellte Kostenposition",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/ExpenseResponse"}
                                }
                            },
                        }
                    },
                }
            },
            "/api/expenses/{id}/documents": {
                "get": {
                    "summary": "Listet Dokumente einer Kostenposition",
                    "parameters": [
                        {
                            "name": "id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer"},
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Dokumentliste",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/ExpenseDocumentListResponse"
                                    }
                                }
                            },
                        },
                        "400": {
                            "description": "Ungültige Anfrage",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                                }
                            },
                        },
                    },
                },
                "post": {
                    "summary": "Lädt ein oder mehrere Dokumente für eine Kostenposition hoch",
                    "parameters": [
                        {
                            "name": "id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer"},
                        }
                    ],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/ExpenseDocumentUploadRequest"
                                }
                            }
                        },
                    },
                    "responses": {
                        "201": {
                            "description": "Hochgeladene Dokumente",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/ExpenseDocumentUploadResponse"
                                    }
                                }
                            },
                        },
                        "400": {
                            "description": "Ungültige Eingabedaten",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                                }
                            },
                        },
                    },
                },
            },
            "/api/expenses/{id}/documents/{document_id}": {
                "delete": {
                    "summary": "Löscht ein Dokument einer Kostenposition",
                    "parameters": [
                        {
                            "name": "id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer"},
                        },
                        {
                            "name": "document_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer"},
                        },
                    ],
                    "responses": {
                        "200": {
                            "description": "Gelöschtes Dokument",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/ExpenseDocumentDeleteResponse"
                                    }
                                }
                            },
                        },
                        "400": {
                            "description": "Ungültige Löschanfrage",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                                }
                            },
                        },
                    },
                }
            },
            "/api/expenses/{id}/documents/{document_id}/download": {
                "get": {
                    "summary": "Lädt ein Dokument einer Kostenposition herunter",
                    "parameters": [
                        {
                            "name": "id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer"},
                        },
                        {
                            "name": "document_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer"},
                        },
                    ],
                    "responses": {
                        "200": {
                            "description": "Dateiinhalt",
                            "content": {
                                "application/octet-stream": {
                                    "schema": {"type": "string", "format": "binary"}
                                }
                            },
                        },
                        "400": {
                            "description": "Ungültige Anfrage",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                                }
                            },
                        },
                    },
                }
            },
            "/api/meters": {
                "post": {
                    "summary": "Erstellt einen neuen Zähler",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/MeterCreateRequest"}
                            }
                        },
                    },
                    "responses": {
                        "201": {
                            "description": "Erstellter Zähler",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/MeterResponse"}
                                }
                            },
                        }
                    },
                }
            },
            "/api/meters/{id}": {
                "put": {
                    "summary": "Aktualisiert einen Zähler",
                    "parameters": [
                        {
                            "name": "id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer"},
                        }
                    ],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/MeterCreateRequest"}
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Aktualisierter Zähler",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/MeterResponse"}
                                }
                            },
                        }
                    },
                }
            },
            "/api/meter-readings": {
                "post": {
                    "summary": "Erfasst einen Zählerstand",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/MeterReadingCreateRequest"}
                            }
                        },
                    },
                    "responses": {
                        "201": {
                            "description": "Erfasster Zählerstand",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/MeterReadingResponse"}
                                }
                            },
                        }
                    },
                }
            },
            "/api/meter-readings/{id}": {
                "delete": {
                    "summary": "Löscht einen Zählerstand",
                    "parameters": [
                        {
                            "name": "id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer"},
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Gelöschter Zählerstand",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/ObjectDeleteResponse"}
                                }
                            },
                        },
                        "400": {
                            "description": "Ungültige Löschanfrage",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                                }
                            },
                        },
                    },
                }
            },
            **build_object_lifecycle_paths(),
            "/api/properties/{id}": {
                **build_object_lifecycle_paths()["/api/properties/{id}"],
                "put": {
                    "summary": "Aktualisiert eine bestehende Anlage",
                    "parameters": [
                        {
                            "name": "id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer"},
                        }
                    ],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/PropertyCreateRequest"}
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Aktualisierte Anlage",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/PropertyResponse"}
                                }
                            },
                        },
                        "400": {
                            "description": "Ungültige Änderungsanfrage",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                                }
                            },
                        },
                    },
                },
            },
            "/api/buildings/{id}": {
                **build_object_lifecycle_paths()["/api/buildings/{id}"],
                "put": {
                    "summary": "Aktualisiert ein bestehendes Gebäude",
                    "parameters": [
                        {
                            "name": "id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer"},
                        }
                    ],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/BuildingCreateRequest"}
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Aktualisiertes Gebäude",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/BuildingResponse"}
                                }
                            },
                        },
                        "400": {
                            "description": "Ungültige Änderungsanfrage",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                                }
                            },
                        },
                    },
                },
            },
            "/api/units/{id}": {
                **build_object_lifecycle_paths()["/api/units/{id}"],
                "put": {
                    "summary": "Aktualisiert eine bestehende Wohnung",
                    "parameters": [
                        {
                            "name": "id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer"},
                        }
                    ],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/UnitCreateRequest"}
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Aktualisierte Wohnung",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/UnitResponse"}
                                }
                            },
                        },
                        "400": {
                            "description": "Ungültige Änderungsanfrage",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                                }
                            },
                        },
                    },
                },
            },
            "/api/rooms/{id}": {
                **build_object_lifecycle_paths()["/api/rooms/{id}"],
                "put": {
                    "summary": "Aktualisiert ein bestehendes Zimmer",
                    "parameters": [
                        {
                            "name": "id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer"},
                        }
                    ],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/RoomCreateRequest"}
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Aktualisiertes Zimmer",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/RoomResponse"}
                                }
                            },
                        },
                        "400": {
                            "description": "Ungültige Änderungsanfrage",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                                }
                            },
                        },
                    },
                },
            },
            "/api/tenants/{id}": {
                "put": {
                    "summary": "Aktualisiert einen bestehenden Mieter",
                    "parameters": [
                        {
                            "name": "id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer"},
                        }
                    ],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/TenantCreateRequest"}
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Aktualisierter Mieter",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/TenantResponse"}
                                }
                            },
                        },
                        "400": {
                            "description": "Ungültige Änderungsanfrage",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                                }
                            },
                        },
                    },
                },
                "delete": {
                    "summary": "Löscht einen Mieter ohne referenzierende Mietverträge",
                    "parameters": [
                        {
                            "name": "id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer"},
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Gelöschter Mieter",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/ObjectDeleteResponse"}
                                }
                            },
                        },
                        "400": {
                            "description": "Ungültige Löschanfrage",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                                }
                            },
                        },
                    },
                },
            },
            "/api/leases/{id}": {
                "put": {
                    "summary": "Aktualisiert einen bestehenden Mietvertrag",
                    "parameters": [
                        {
                            "name": "id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer"},
                        }
                    ],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/LeaseCreateRequest"}
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Aktualisierter Mietvertrag",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/LeaseResponse"}
                                }
                            },
                        },
                        "400": {
                            "description": "Ungültige Änderungsanfrage",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                                }
                            },
                        },
                    },
                },
                "delete": {
                    "summary": "Löscht einen bestehenden Mietvertrag",
                    "parameters": [
                        {
                            "name": "id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer"},
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Gelöschter Mietvertrag",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/ObjectDeleteResponse"}
                                }
                            },
                        },
                        "400": {
                            "description": "Ungültige Löschanfrage",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                                }
                            },
                        },
                    },
                },
            },
            "/api/expenses/{id}": {
                **build_object_lifecycle_paths()["/api/expenses/{id}"],
                "put": {
                    "summary": "Aktualisiert eine bestehende Kostenposition",
                    "parameters": [
                        {
                            "name": "id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer"},
                        }
                    ],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ExpenseCreateRequest"}
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Aktualisierte Kostenposition",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/ExpenseResponse"}
                                }
                            },
                        },
                        "400": {
                            "description": "Ungültige Änderungsanfrage",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                                }
                            },
                        },
                    },
                },
            },
        },
        "components": {
            "schemas": {
                "OverviewResponse": {
                    "type": "object",
                    "properties": {
                        "summary": {"type": "object"},
                        "properties": {"type": "array", "items": {"type": "object"}},
                        "buildings": {"type": "array", "items": {"type": "object"}},
                        "units": {"type": "array", "items": {"type": "object"}},
                        "rooms": {"type": "array", "items": {"type": "object"}},
                        "meters": {"type": "array", "items": {"type": "object"}},
                        "meter_readings": {"type": "array", "items": {"type": "object"}},
                        "tenants": {"type": "array", "items": {"type": "object"}},
                        "leases": {"type": "array", "items": {"type": "object"}},
                        "expenses": {"type": "array", "items": {"type": "object"}},
                        "expense_categories": {"type": "array", "items": {"type": "object"}},
                        "depreciation_assets": {"type": "array", "items": {"type": "object"}},
                    },
                },
                "PropertyCreateRequest": {
                    "type": "object",
                    "required": ["organization_id", "name", "street", "city", "postal_code"],
                    "properties": {
                        "organization_id": {"type": "integer"},
                        "name": {"type": "string"},
                        "street": {"type": "string"},
                        "city": {"type": "string"},
                        "postal_code": {"type": "string"},
                    },
                },
                "PropertyResponse": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "organization_id": {"type": "integer"},
                        "name": {"type": "string"},
                        "street": {"type": "string"},
                        "city": {"type": "string"},
                        "postal_code": {"type": "string"},
                    },
                },
                "BuildingCreateRequest": {
                    "type": "object",
                    "required": ["name", "street", "city", "postal_code"],
                    "properties": {
                        "property_id": {"type": ["integer", "null"]},
                        "name": {"type": "string"},
                        "year_built": {"type": ["integer", "null"]},
                        "street": {"type": "string"},
                        "city": {"type": "string"},
                        "postal_code": {"type": "string"},
                    },
                },
                "BuildingResponse": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "property_id": {"type": ["integer", "null"]},
                        "name": {"type": "string"},
                        "year_built": {"type": ["integer", "null"]},
                        "street": {"type": "string"},
                        "city": {"type": "string"},
                        "postal_code": {"type": "string"},
                    },
                },
                "UnitCreateRequest": {
                    "type": "object",
                    "required": ["label", "area_sqm", "room_count", "street", "city", "postal_code"],
                    "properties": {
                        "building_id": {"type": ["integer", "null"]},
                        "label": {"type": "string"},
                        "area_sqm": {"type": "string"},
                        "room_count": {"type": "integer"},
                        "street": {"type": "string"},
                        "city": {"type": "string"},
                        "postal_code": {"type": "string"},
                    },
                },
                "UnitResponse": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "building_id": {"type": ["integer", "null"]},
                        "label": {"type": "string"},
                        "area_sqm": {"type": "string"},
                        "room_count": {"type": "integer"},
                        "street": {"type": "string"},
                        "city": {"type": "string"},
                        "postal_code": {"type": "string"},
                    },
                },
                "RoomCreateRequest": {
                    "type": "object",
                    "required": ["unit_id", "label"],
                    "properties": {
                        "unit_id": {"type": "integer"},
                        "label": {"type": "string"},
                        "area_sqm": {"type": ["string", "null"]},
                    },
                },
                "RoomResponse": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "unit_id": {"type": "integer"},
                        "label": {"type": "string"},
                        "area_sqm": {"type": ["string", "null"]},
                    },
                },
                "TenantCreateRequest": {
                    "type": "object",
                    "required": ["full_name"],
                    "properties": {
                        "full_name": {"type": "string"},
                        "email": {"type": ["string", "null"]},
                        "phone": {"type": ["string", "null"]},
                    },
                },
                "TenantResponse": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "full_name": {"type": "string"},
                        "email": {"type": ["string", "null"]},
                        "phone": {"type": ["string", "null"]},
                    },
                },
                "LeaseCreateRequest": {
                    "type": "object",
                    "required": [
                        "tenant_id",
                        "rent_cold",
                        "additional_charges_advance",
                        "occupant_count",
                        "start_date",
                    ],
                    "properties": {
                        "unit_id": {"type": ["integer", "null"]},
                        "room_id": {"type": ["integer", "null"]},
                        "tenant_id": {"type": "integer"},
                        "rent_cold": {"type": "string"},
                        "additional_charges_advance": {"type": "string"},
                        "occupant_count": {"type": "integer"},
                        "start_date": {"type": "string", "format": "date"},
                        "end_date": {"type": ["string", "null"], "format": "date"},
                        "status": {"type": "string"},
                    },
                },
                "LeaseResponse": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "unit_id": {"type": "integer"},
                        "room_id": {"type": ["integer", "null"]},
                        "tenant_id": {"type": "integer"},
                        "rent_cold": {"type": "string"},
                        "additional_charges_advance": {"type": "string"},
                        "occupant_count": {"type": "integer"},
                        "start_date": {"type": "string", "format": "date"},
                        "end_date": {"type": ["string", "null"], "format": "date"},
                        "status": {"type": "string"},
                    },
                },
                "MeterCreateRequest": {
                    "type": "object",
                    "required": ["object_type", "object_id", "label", "unit"],
                    "properties": {
                        "object_type": {
                            "type": "string",
                            "enum": ["property", "building", "unit", "room"],
                        },
                        "object_id": {"type": "integer"},
                        "label": {"type": "string"},
                        "meter_type": {"type": ["string", "null"]},
                        "unit": {"type": "string"},
                        "serial_number": {"type": ["string", "null"]},
                    },
                },
                "MeterResponse": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "property_id": {"type": ["integer", "null"]},
                        "object_type": {"type": "string"},
                        "object_id": {"type": "integer"},
                        "label": {"type": "string"},
                        "meter_type": {"type": ["string", "null"]},
                        "unit": {"type": "string"},
                        "serial_number": {"type": ["string", "null"]},
                    },
                },
                "MeterReadingCreateRequest": {
                    "type": "object",
                    "required": ["meter_id", "reading_date", "reading_value"],
                    "properties": {
                        "meter_id": {"type": "integer"},
                        "reading_date": {"type": "string", "format": "date"},
                        "reading_value": {"type": "string"},
                    },
                },
                "MeterReadingResponse": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "meter_id": {"type": "integer"},
                        "reading_date": {"type": "string", "format": "date"},
                        "reading_value": {"type": "string"},
                    },
                },
                "SettlementResponse": {
                    "type": "object",
                    "properties": {
                        "property_id": {"type": "integer"},
                        "period_start": {"type": "string", "format": "date"},
                        "period_end": {"type": "string", "format": "date"},
                        "results": {"type": "array", "items": {"type": "object"}},
                        "totals": {"type": "object"},
                    },
                },
                "DepreciationScheduleResponse": {
                    "type": "object",
                    "properties": {
                        "year": {"type": "integer"},
                        "rows": {"type": "array", "items": {"type": "object"}},
                        "total": {"type": "string"},
                    },
                },
                "ExpenseCreateRequest": {
                    "type": "object",
                    "required": [
                        "object_type",
                        "object_id",
                        "amount",
                        "allocation_method",
                    ],
                    "properties": {
                        "object_type": {
                            "type": "string",
                            "enum": ["property", "building", "unit", "room"],
                        },
                        "object_id": {"type": "integer"},
                        "expense_category": {"type": "string"},
                        "beneficiary_name": {"type": "string"},
                        "label": {"type": "string"},
                        "amount": {"type": "string"},
                        "allocation_method": {
                            "type": "string",
                            "enum": ["area", "unit_count", "occupants"],
                        },
                        "charge_type": {
                            "type": "string",
                            "enum": ["one_time", "monthly", "quarterly", "yearly", "consumption"],
                        },
                        "recurrence": {
                            "type": "string",
                            "enum": ["one_time", "recurring"],
                        },
                        "interval": {
                            "type": "string",
                            "enum": ["monthly", "quarterly", "yearly"],
                        },
                        "meter_id": {"type": ["integer", "null"]},
                        "consumption_unit": {"type": "string"},
                        "consumption_value": {"type": "string"},
                        "conversion_factor": {"type": "string"},
                        "booking_date": {"type": "string", "format": "date"},
                        "period_start": {"type": "string", "format": "date"},
                        "period_end": {"type": "string", "format": "date"},
                    },
                },
                "ExpenseResponse": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "object_type": {"type": "string"},
                        "object_id": {"type": "integer"},
                        "expense_category": {"type": "string"},
                        "beneficiary_name": {"type": "string"},
                        "label": {"type": "string"},
                        "amount": {"type": "string"},
                        "allocation_method": {"type": "string"},
                        "charge_type": {"type": "string"},
                        "recurrence": {"type": "string"},
                        "interval": {"type": "string"},
                        "meter_id": {"type": ["integer", "null"]},
                        "meter_unit": {"type": ["string", "null"]},
                        "consumption_unit": {"type": ["string", "null"]},
                        "conversion_factor": {"type": ["string", "null"]},
                        "consumption_value": {"type": ["string", "null"]},
                        "effective_consumption_value": {"type": ["string", "null"]},
                        "total_amount": {"type": ["string", "null"]},
                        "booking_date": {"type": ["string", "null"], "format": "date"},
                        "period_start": {"type": "string", "format": "date"},
                        "period_end": {"type": ["string", "null"], "format": "date"},
                        "is_open_ended": {"type": "boolean"},
                    },
                },
                "HealthResponse": {
                    "type": "object",
                    "properties": {
                        "status": {"type": "string"},
                        "reachable": {"type": "boolean"},
                        "checked_at": {"type": ["string", "null"]},
                    },
                },
                "PaperlessSettingsUpdateRequest": {
                    "type": "object",
                    "required": ["base_url"],
                    "properties": {
                        "base_url": {"type": "string"},
                        "api_token": {"type": "string"},
                    },
                },
                "PaperlessSettingsResponse": {
                    "type": "object",
                    "properties": {
                        "base_url": {"type": "string"},
                        "token_present": {"type": "boolean"},
                        "token_masked": {"type": ["string", "null"]},
                        "updated_at": {"type": ["string", "null"]},
                    },
                },
                "PaperlessStatusResponse": {
                    "type": "object",
                    "properties": {
                        "configured": {"type": "boolean"},
                        "reachable": {"type": "boolean"},
                        "message": {"type": "string"},
                        "checked_at": {"type": ["string", "null"]},
                    },
                },
                "ApplicationSettingsUpdateRequest": {
                    "type": "object",
                    "required": ["show_delete_actions"],
                    "properties": {
                        "show_delete_actions": {"type": "boolean"},
                    },
                },
                "ApplicationSettingsResponse": {
                    "type": "object",
                    "properties": {
                        "show_delete_actions": {"type": "boolean"},
                        "updated_at": {"type": ["string", "null"]},
                    },
                },
                "ApplicationExportResponse": {
                    "type": "object",
                    "properties": {
                        "format_version": {"type": "integer"},
                        "exported_at": {"type": "string"},
                        "table_count": {"type": "integer"},
                        "row_count": {"type": "integer"},
                        "tables": {
                            "type": "object",
                            "additionalProperties": {
                                "type": "array",
                                "items": {"type": "object"},
                            },
                        },
                    },
                },
                "ApplicationImportRequest": {
                    "type": "object",
                    "required": ["format_version", "tables"],
                    "properties": {
                        "format_version": {"type": "integer"},
                        "tables": {
                            "type": "object",
                            "additionalProperties": {
                                "type": "array",
                                "items": {"type": "object"},
                            },
                        },
                    },
                },
                "ApplicationImportResponse": {
                    "type": "object",
                    "properties": {
                        "format_version": {"type": "integer"},
                        "imported_at": {"type": "string"},
                        "table_count": {"type": "integer"},
                        "row_count": {"type": "integer"},
                    },
                },
                "LinkedDocumentUploadEntry": {
                    "type": "object",
                    "properties": {
                        "filename": {"type": "string"},
                        "content_type": {"type": "string"},
                        "content_base64": {"type": "string"},
                        "paperless_document_id": {"type": "string"},
                    },
                    "anyOf": [
                        {"required": ["filename", "content_base64"]},
                        {"required": ["paperless_document_id"]},
                    ],
                },
                "LinkedDocumentUploadRequest": {
                    "type": "object",
                    "required": ["documents"],
                    "properties": {
                        "documents": {
                            "type": "array",
                            "items": {"$ref": "#/components/schemas/LinkedDocumentUploadEntry"},
                        }
                    },
                },
                "LinkedDocumentResponse": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "resource_type": {"type": "string"},
                        "resource_id": {"type": "integer"},
                        "filename": {"type": "string"},
                        "content_type": {"type": "string"},
                        "content_size": {"type": "integer"},
                        "paperless_document_id": {"type": ["string", "null"]},
                        "paperless_task_id": {"type": ["string", "null"]},
                        "paperless_reference_url": {"type": ["string", "null"]},
                        "upload_status": {"type": "string"},
                        "upload_error": {"type": ["string", "null"]},
                        "created_at": {"type": "string"},
                    },
                },
                "LinkedDocumentListResponse": {
                    "type": "object",
                    "properties": {
                        "resource_type": {"type": "string"},
                        "resource_id": {"type": "integer"},
                        "documents": {
                            "type": "array",
                            "items": {"$ref": "#/components/schemas/LinkedDocumentResponse"},
                        },
                    },
                },
                "LinkedDocumentDeleteResponse": {
                    "type": "object",
                    "properties": {
                        "resource_type": {"type": "string"},
                        "resource_id": {"type": "integer"},
                        "document_id": {"type": "integer"},
                        "deleted": {"type": "boolean"},
                    },
                },
                "ExpenseDocumentUploadEntry": {
                    "type": "object",
                    "properties": {
                        "filename": {"type": "string"},
                        "content_type": {"type": "string"},
                        "content_base64": {"type": "string"},
                        "paperless_document_id": {"type": "string"},
                    },
                    "anyOf": [
                        {"required": ["filename", "content_base64"]},
                        {"required": ["paperless_document_id"]},
                    ],
                },
                "ExpenseDocumentUploadRequest": {
                    "type": "object",
                    "required": ["documents"],
                    "properties": {
                        "documents": {
                            "type": "array",
                            "items": {"$ref": "#/components/schemas/ExpenseDocumentUploadEntry"},
                        }
                    },
                },
                "ExpenseDocumentResponse": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "expense_id": {"type": "integer"},
                        "filename": {"type": "string"},
                        "content_type": {"type": "string"},
                        "content_size": {"type": "integer"},
                        "paperless_document_id": {"type": ["string", "null"]},
                        "paperless_task_id": {"type": ["string", "null"]},
                        "paperless_reference_url": {"type": ["string", "null"]},
                        "upload_status": {"type": "string"},
                        "upload_error": {"type": ["string", "null"]},
                        "created_at": {"type": "string"},
                    },
                },
                "ExpenseDocumentUploadResponse": {
                    "type": "object",
                    "properties": {
                        "expense_id": {"type": "integer"},
                        "documents": {
                            "type": "array",
                            "items": {"$ref": "#/components/schemas/ExpenseDocumentResponse"},
                        },
                    },
                },
                "ExpenseDocumentListResponse": {
                    "type": "object",
                    "properties": {
                        "expense_id": {"type": "integer"},
                        "documents": {
                            "type": "array",
                            "items": {"$ref": "#/components/schemas/ExpenseDocumentResponse"},
                        },
                    },
                },
                "ExpenseDocumentDeleteResponse": {
                    "type": "object",
                    "properties": {
                        "expense_id": {"type": "integer"},
                        "document_id": {"type": "integer"},
                        "deleted": {"type": "boolean"},
                    },
                },
                "ObjectArchiveResponse": {
                    "type": "object",
                    "properties": {
                        "resource": {"type": "string"},
                        "id": {"type": "integer"},
                        "is_archived": {"type": "integer"},
                        "archived_at": {"type": ["string", "null"]},
                    },
                },
                "ObjectDeleteResponse": {
                    "type": "object",
                    "properties": {
                        "resource": {"type": "string"},
                        "id": {"type": "integer"},
                        "deleted": {"type": "boolean"},
                    },
                },
                "ErrorResponse": {
                    "type": "object",
                    "properties": {
                        "error": {"type": "string"},
                    },
                },
            }
        },
    }
