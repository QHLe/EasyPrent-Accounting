(function () {
  if (!window.React) {
    return;
  }

  const e = React.createElement;
  const Fragment = React.Fragment;
  const domain = window.EasyPrentAppDomain || {};
  const formsModule = window.EasyPrentAppForms || {};
  const buildObjectTargetValue = domain.buildObjectTargetValue;
  const formatAddress = domain.formatAddress;
  const formatDisplayName = domain.formatDisplayName;
  const formatExpenseAmountValue = domain.formatExpenseAmountValue;
  const formatExpenseBillingType = domain.formatExpenseBillingType;
  const formatExpenseCadence = domain.formatExpenseCadence;
  const formatExpenseCategoryLabel = domain.formatExpenseCategoryLabel;
  const formatExpenseTargetLabel = domain.formatExpenseTargetLabel;
  const formatExpenseWindow = domain.formatExpenseWindow;
  const formatObjectTypeLabel = domain.formatObjectTypeLabel;
  const sortExpensesByEndDateDesc = domain.sortExpensesByEndDateDesc;
  const table = domain.table;
  const renderExpenseForm = formsModule.renderExpenseForm;

  function normalizedFilterText(value) {
    return String(value || "").trim().toLowerCase();
  }

  function matchesManagementFilter(managementListFilters, tabKey, values) {
    const query = normalizedFilterText((managementListFilters || {})[tabKey]);
    if (!query) {
      return true;
    }
    return values.some(function (value) {
      return normalizedFilterText(value).indexOf(query) >= 0;
    });
  }

  function objectStatusLabel(item) {
    return item && item.is_archived ? "Archiviert" : "Aktiv";
  }

  function buildManagementFilterToolbar(config) {
    return e(
      "div",
      { className: "stack" },
      e("h3", null, config.title),
      e(
        "div",
        { className: "chart-controls" },
        e(
          "label",
          null,
          "Filter",
          e("input", {
            type: "text",
            value: config.value,
            placeholder: config.placeholder,
            onChange: function (event) {
              config.onChange(event.target.value);
            },
          })
        )
      )
    );
  }

  function buildExpenseFilterToolbar(config) {
    return e(
      "div",
      { className: "stack" },
      e("h3", null, "Kostenliste filtern"),
      e(
        "div",
        { className: "chart-controls" },
        e(
          "label",
          null,
          "Jahr",
          e("input", {
            type: "number",
            min: "1900",
            max: "9999",
            step: "1",
            value: config.filters.year,
            onChange: function (event) {
              config.onChange("year", event.target.value);
            },
          })
        ),
        e(
          "label",
          null,
          "Zielobjekt-Filter",
          e(
            "select",
            {
              value: config.filters.target,
              onChange: function (event) {
                config.onChange("target", event.target.value);
              },
            },
            e("option", { value: "" }, "Alle Zielobjekte"),
            config.expenseListTargetOptions
          )
        ),
        e(
          "label",
          null,
          "Kostenart-Filter",
          e(
            "select",
            {
              value: config.filters.expense_category,
              onChange: function (event) {
                config.onChange("expense_category", event.target.value);
              },
            },
            e("option", { value: "" }, "Alle Kostenarten"),
            config.expenseCategoryFilterOptions
          )
        )
      )
    );
  }

  function buildOverviewRows(props) {
    const overview = props.overview || {};
    const selectedMeterId = props.selectedMeterId;
    const onMeterSelect = props.onMeterSelect || function () {};

    const roleItems = (overview.roles || []).map(function (role, index) {
      return e(
        "li",
        { key: role.email || index },
        role.full_name + " (" + role.role + ") - " + role.organization_name
      );
    });

    const propertyRows = (overview.properties || []).map(function (property) {
      return e(
        "tr",
        { key: property.id },
        e("td", null, String(property.id)),
        e("td", null, formatDisplayName(property)),
        e("td", null, property.organization_name),
        e("td", null, formatAddress(property))
      );
    });
    const buildingRows = (overview.buildings || []).map(function (building) {
      return e(
        "tr",
        { key: building.id },
        e("td", null, String(building.id)),
        e("td", null, formatDisplayName(building)),
        e("td", null, building.property_name || "Standalone"),
        e("td", null, formatAddress(building))
      );
    });
    const unitRows = (overview.units || []).map(function (unit) {
      return e(
        "tr",
        { key: unit.id },
        e("td", null, String(unit.id)),
        e("td", null, formatDisplayName(unit)),
        e("td", null, unit.building_name || "Standalone"),
        e("td", null, formatAddress(unit))
      );
    });
    const roomRows = (overview.rooms || []).map(function (room) {
      return e(
        "tr",
        { key: room.id },
        e("td", null, String(room.id)),
        e("td", null, formatDisplayName(room)),
        e("td", null, room.unit_label || String(room.unit_id)),
        e(
          "td",
          null,
          room.area_sqm == null || room.area_sqm === "" ? "-" : String(room.area_sqm) + " m²"
        )
      );
    });
    const meterRows = (overview.meters || []).map(function (meter) {
      return e(
        "tr",
        {
          key: meter.id,
          className:
            "selectable-row" + (String(selectedMeterId) === String(meter.id) ? " selected" : ""),
          onClick: function () {
            onMeterSelect(meter.id);
          },
        },
        e("td", null, String(meter.id)),
        e("td", null, formatDisplayName(meter)),
        e("td", null, formatObjectTypeLabel(meter.object_type)),
        e("td", null, meter.object_name || ("ID " + String(meter.object_id))),
        e("td", null, meter.unit),
        e("td", null, meter.latest_reading_value == null ? "-" : String(meter.latest_reading_value))
      );
    });
    const leaseRows = (overview.leases || []).map(function (lease) {
      return e(
        "tr",
        { key: lease.id },
        e("td", null, lease.tenant_name),
        e("td", null, lease.rental_object_label || lease.unit_label),
        e("td", null, lease.start_date),
        e("td", null, String(lease.rent_cold)),
        e("td", null, String(lease.additional_charges_advance))
      );
    });
    const expenseRows = (overview.expenses || [])
      .slice()
      .sort(sortExpensesByEndDateDesc)
      .map(function (expense) {
        return e(
          "tr",
          { key: expense.id },
          e("td", null, formatExpenseCategoryLabel(expense)),
          e("td", null, expense.beneficiary_name || "Nicht gepflegt"),
          e("td", null, formatExpenseBillingType(expense)),
          e("td", null, formatExpenseAmountValue(expense)),
          e("td", null, expense.total_amount == null ? "-" : expense.total_amount),
          e("td", null, expense.period_start),
          e("td", null, expense.period_end)
        );
      });
    const settlementRows = ((props.settlement && props.settlement.results) || []).map(function (row) {
      const documentParameters = {
        lease_id: row.lease_id,
        period_start: props.settlement.period_start,
        period_end: props.settlement.period_end,
      };
      if (props.settlement.property_id != null) {
        documentParameters.property_id = props.settlement.property_id;
      }
      if (props.settlement.unit_id != null) {
        documentParameters.unit_id = props.settlement.unit_id;
      }
      const documentUrl =
        "/api/settlements/document.ods?" +
        new URLSearchParams(documentParameters).toString();
      return e(
        "tr",
        { key: row.lease_id },
        e("td", null, row.tenant_name),
        e("td", null, row.unit_label),
        e(
          "td",
          null,
          String(row.billing_period_start || "") +
            " – " +
            String(row.billing_period_end || "")
        ),
        e("td", null, row.allocated_costs),
        e("td", null, row.advances_paid == null ? "-" : row.advances_paid),
        e("td", null, row.balance == null ? "-" : row.balance),
        e(
          "td",
          null,
          e(
            "a",
            { className: "action-button secondary settlement-document-download", href: documentUrl },
            "ODS-Abrechnung herunterladen"
          )
        )
      );
    });
    const depreciationRows = ((props.depreciation && props.depreciation.rows) || []).map(function (row) {
      return e(
        "tr",
        { key: row.asset_name },
        e("td", null, row.asset_name),
        e("td", null, row.method),
        e("td", null, row.depreciable_basis),
        e("td", null, String(row.months_in_year)),
        e("td", null, row.yearly_depreciation)
      );
    });

    return {
      roleItems: roleItems,
      propertyRows: propertyRows,
      buildingRows: buildingRows,
      unitRows: unitRows,
      roomRows: roomRows,
      meterRows: meterRows,
      leaseRows: leaseRows,
      expenseRows: expenseRows,
      settlementRows: settlementRows,
      depreciationRows: depreciationRows,
    };
  }

  function buildMeterData(props) {
    const overview = props.overview || {};
    const selectedMeterId = props.selectedMeterId;
    const onDeleteMeterReading = props.onDeleteMeterReading || function () {};
    const saving = !!props.saving;
    const loading = !!props.loading;
    const showDeleteActions = props.showDeleteActions !== false;

    const selectedMeter = (overview.meters || []).find(function (meter) {
      return String(meter.id) === String(selectedMeterId);
    });
    function sortMeterReadingsByDateDesc(left, right) {
      if (left.reading_date === right.reading_date) {
        return Number(right.id) - Number(left.id);
      }
      return left.reading_date < right.reading_date ? 1 : -1;
    }

    const selectedMeterReadings = (overview.meter_readings || [])
      .filter(function (reading) {
        return String(reading.meter_id) === String(selectedMeterId);
      });
    const historyMeterReadings = selectedMeterId
      ? selectedMeterReadings.slice().sort(sortMeterReadingsByDateDesc)
      : (overview.meter_readings || []).slice().sort(sortMeterReadingsByDateDesc);
    const meterReadingRows = historyMeterReadings.map(function (reading) {
      return e(
        "tr",
        { key: "meter-reading-" + String(reading.id) },
        e("td", null, reading.meter_label || "-"),
        e("td", null, reading.reading_date),
        e("td", null, String(reading.reading_value)),
        e("td", null, reading.meter_unit || "-"),
        e("td", null, reading.object_name || ("ID " + String(reading.object_id))),
        e(
          "td",
          null,
          showDeleteActions
            ? e(
                "button",
                {
                  type: "button",
                  className: "action-button danger",
                  disabled: saving || loading,
                  onClick: function () {
                    onDeleteMeterReading(reading);
                  },
                },
                "Zählerstand löschen"
              )
            : "-"
        )
      );
    });

    return {
      selectedMeter: selectedMeter,
      selectedMeterReadings: selectedMeterReadings,
      historyMeterReadings: historyMeterReadings,
      meterReadingRows: meterReadingRows,
    };
  }

  function expenseOverlapsYear(expense, year) {
    if (!/^\d{4}$/.test(String(year || ""))) {
      return true;
    }

    const yearStart = String(year) + "-01-01";
    const yearEnd = String(year) + "-12-31";
    const startDate = expense.period_start || expense.booking_date;
    const endDate = expense.is_open_ended
      ? ""
      : expense.period_end || (expense.charge_type === "one_time" ? expense.booking_date : "");

    return !!startDate && startDate <= yearEnd && (!endDate || endDate >= yearStart);
  }

  function buildFilteredExpenses(expenses, expenseListFilters) {
    const filters = expenseListFilters || {};
    const normalizedExpenseCategoryFilter = normalizedFilterText(filters.expense_category);

    return (expenses || []).filter(function (expense) {
      const targetMatch =
        filters.target === "" ||
        buildObjectTargetValue(expense.object_type, expense.object_id) === filters.target;
      const categoryMatch =
        normalizedExpenseCategoryFilter === "" ||
        normalizedFilterText(expense.expense_category || expense.label || "") ===
          normalizedExpenseCategoryFilter;
      return targetMatch && categoryMatch && expenseOverlapsYear(expense, filters.year);
    });
  }

  function buildManagementInlineEditorRow(props) {
    return e(
      "tr",
      { key: props.rowKey },
      e(
        "td",
        { colSpan: props.previewHeadersLength },
        e(
          "div",
          { className: "inline-editor" },
          e("h4", null, props.heading),
          props.form
        )
      )
    );
  }

  function appendManagementPreviewRow(previewRows, props) {
    previewRows.push(props.row);
    if (!props.isEditing || !props.inlineEditorForm) {
      return;
    }
    previewRows.push(
      buildManagementInlineEditorRow({
        rowKey: props.inlineRowKey,
        previewHeadersLength: props.previewHeadersLength,
        heading: props.inlineEditorHeading,
        form: props.inlineEditorForm,
      })
    );
  }

  function sortByNumericId(left, right) {
    return Number(left.id || 0) - Number(right.id || 0);
  }

  function formatAreaLabel(value, prefixLabel) {
    if (value == null || value === "") {
      return "";
    }
    const normalizedPrefix = prefixLabel ? String(prefixLabel) + ": " : "";
    return normalizedPrefix + String(value) + " m²";
  }

  function formatObjectParentLabel(tabKey, entity) {
    if (tabKey === "properties") {
      return entity.organization_name ? "Organisation: " + entity.organization_name : "Kein Elternobjekt";
    }
    if (tabKey === "buildings") {
      return entity.property_name ? "Anlage: " + entity.property_name : "Kein Elternobjekt";
    }
    if (tabKey === "units") {
      const path = [];
      if (entity.building_name) {
        path.push("Gebäude: " + entity.building_name);
      }
      if (entity.property_name) {
        path.push("Anlage: " + entity.property_name);
      }
      return path.length ? path.join(" | ") : "Kein Elternobjekt";
    }
    if (tabKey === "rooms") {
      const path = [];
      if (entity.unit_label) {
        path.push("Wohnung: " + entity.unit_label);
      }
      if (entity.building_name) {
        path.push("Gebäude: " + entity.building_name);
      }
      if (entity.property_name) {
        path.push("Anlage: " + entity.property_name);
      }
      return path.length ? path.join(" | ") : "Kein Elternobjekt";
    }
    return "Kein Elternobjekt";
  }

  function formatObjectChildrenLabel(tabKey, entity) {
    if (tabKey === "properties") {
      return [
        String(entity.building_count || 0) + " Gebäude",
        String(entity.unit_count || 0) + " Wohnungen",
        String(entity.room_count || 0) + " Zimmer",
      ].join(" | ");
    }
    if (tabKey === "buildings") {
      return [
        String(entity.unit_count || 0) + " Wohnungen",
        String(entity.room_count || 0) + " Zimmer",
      ].join(" | ");
    }
    if (tabKey === "units") {
      return String(entity.actual_room_count || 0) + " von " + String(entity.room_count || 0) + " Zimmern";
    }
    return "Keine";
  }

  function formatObjectDetailsLabel(tabKey, entity) {
    const details = [];
    if (tabKey === "properties") {
      details.push(formatAddress(entity));
      details.push(String(entity.expense_count || 0) + " Kosten");
    } else if (tabKey === "buildings") {
      details.push(formatAddress(entity));
      if (entity.year_built != null && entity.year_built !== "") {
        details.push("Baujahr: " + String(entity.year_built));
      }
    } else if (tabKey === "units") {
      details.push(formatAddress(entity));
      const areaLabel = formatAreaLabel(entity.area_sqm, "Fläche");
      if (areaLabel) {
        details.push(areaLabel);
      }
      details.push(
        "Zimmer: " + String(entity.actual_room_count || 0) + "/" + String(entity.room_count || 0)
      );
    } else if (tabKey === "rooms") {
      const roomAreaLabel = formatAreaLabel(entity.area_sqm, "Wohnfläche");
      if (roomAreaLabel) {
        details.push(roomAreaLabel);
      }
      if (entity.unit_label) {
        details.push("Wohnung: " + entity.unit_label);
      }
    }
    return details.filter(Boolean).join(" | ") || "-";
  }

  function objectHierarchyName(label, level) {
    return e(
      "span",
      {
        style: {
          display: "inline-block",
          paddingLeft: level * 20,
        },
      },
      label
    );
  }

  function buildHierarchicalObjectEntries(overview) {
    const properties = (overview.properties || []).slice().sort(sortByNumericId);
    const buildings = (overview.buildings || []).slice().sort(sortByNumericId);
    const units = (overview.units || []).slice().sort(sortByNumericId);
    const rooms = (overview.rooms || []).slice().sort(sortByNumericId);
    const buildingsByProperty = {};
    const standaloneBuildings = [];
    const unitsByBuilding = {};
    const standaloneUnits = [];
    const roomsByUnit = {};
    const entries = [];

    buildings.forEach(function (building) {
      if (building.property_id == null) {
        standaloneBuildings.push(building);
        return;
      }
      const propertyKey = String(building.property_id);
      if (!buildingsByProperty[propertyKey]) {
        buildingsByProperty[propertyKey] = [];
      }
      buildingsByProperty[propertyKey].push(building);
    });

    units.forEach(function (unit) {
      if (unit.building_id == null) {
        standaloneUnits.push(unit);
        return;
      }
      const buildingKey = String(unit.building_id);
      if (!unitsByBuilding[buildingKey]) {
        unitsByBuilding[buildingKey] = [];
      }
      unitsByBuilding[buildingKey].push(unit);
    });

    rooms.forEach(function (room) {
      const unitKey = String(room.unit_id);
      if (!roomsByUnit[unitKey]) {
        roomsByUnit[unitKey] = [];
      }
      roomsByUnit[unitKey].push(room);
    });

    function appendRoomEntries(unit, level) {
      (roomsByUnit[String(unit.id)] || []).forEach(function (room) {
        entries.push({
          tabKey: "rooms",
          entity: room,
          level: level,
          typeLabel: "Zimmer",
        });
      });
    }

    function appendUnitEntries(unitList, level) {
      unitList.forEach(function (unit) {
        entries.push({
          tabKey: "units",
          entity: unit,
          level: level,
          typeLabel: "Wohnung",
        });
        appendRoomEntries(unit, level + 1);
      });
    }

    function appendBuildingEntries(buildingList, level) {
      buildingList.forEach(function (building) {
        entries.push({
          tabKey: "buildings",
          entity: building,
          level: level,
          typeLabel: "Gebäude",
        });
        appendUnitEntries((unitsByBuilding[String(building.id)] || []).slice().sort(sortByNumericId), level + 1);
      });
    }

    properties.forEach(function (property) {
      entries.push({
        tabKey: "properties",
        entity: property,
        level: 0,
        typeLabel: "Anlage",
      });
      appendBuildingEntries((buildingsByProperty[String(property.id)] || []).slice().sort(sortByNumericId), 1);
    });

    appendBuildingEntries(standaloneBuildings, 0);
    appendUnitEntries(standaloneUnits, 0);

    return entries;
  }

  function buildExpenseInlineEditor(props) {
    const expense = props.expense;
    const documents = props.expenseDocuments || [];
    const uploadFiles = props.expenseUploadFiles || [];
    const showDeleteActions = props.showDeleteActions !== false;
    const normalizedExpenseDocumentReferenceId = String(
      props.expenseDocumentReferenceId || ""
    ).trim();

    return e(
      "tr",
      { key: "expense-preview-edit-" + String(expense.id) },
      e(
        "td",
        { colSpan: props.previewHeadersLength },
        e(
          "div",
          { className: "inline-editor" },
          e("h4", null, "Kosten bearbeiten"),
          typeof renderExpenseForm === "function"
            ? renderExpenseForm({
                formState: props.expenseEditForm,
                onSubmit: function (event) {
                  props.onExpenseUpdateSubmit(event, expense.id);
                },
                setField: props.onExpenseEditFieldChange,
                setExpenseCategory: props.onExpenseEditCategoryChange,
                setTargetValue: props.onExpenseEditTargetChange,
                setMeterId: props.onExpenseEditMeterChange,
                submitLabel: "Änderungen speichern",
                extraAction: e(
                  Fragment,
                  null,
                  e(
                    "button",
                    {
                      type: "button",
                      className: "action-button secondary",
                      disabled: props.saving || props.loading,
                      onClick: function () {
                        props.onExpenseArchive(expense);
                      },
                    },
                    "Kosten archivieren"
                  ),
                  e(
                    "button",
                    {
                      type: "button",
                      className: "action-button secondary",
                      disabled: props.saving || props.loading,
                      onClick: function () {
                        props.onExpenseEditCancel();
                      },
                    },
                    "Abbrechen"
                  )
                ),
                overview: props.overview,
                expenseTargetOptions: props.expenseTargetOptions,
                expenseCategorySuggestions: props.expenseCategorySuggestions,
                meterOptions: props.meterOptions,
                calculateMeterConsumptionValue: props.calculateMeterConsumptionValue,
                saving: props.saving,
                loading: props.loading,
              })
            : null,
          e(
            "div",
            { className: "stack" },
            e("h4", null, "Dokumente"),
            e(
              "p",
              { className: "hint" },
              "Vorhandene Paperless-Dokumente können direkt per Dokument-ID verknüpft werden."
            ),
            e(
              "label",
              null,
              "Paperless Dokument-ID",
              e("input", {
                type: "text",
                value: props.expenseDocumentReferenceId || "",
                placeholder: "4711",
                onChange: function (event) {
                  props.onExpenseDocumentReferenceIdChange(event.target.value);
                },
                disabled: props.saving || props.loading,
              })
            ),
            e(
              "div",
              { className: "inline-actions" },
              e(
                "button",
                {
                  type: "button",
                  disabled:
                    props.saving ||
                    props.loading ||
                    normalizedExpenseDocumentReferenceId === "",
                  onClick: function () {
                    props.onExpenseDocumentReferenceCreate(expense.id);
                  },
                },
                "Dokumenten-ID hinzufügen"
              )
            ),
            e(
              "label",
              null,
              "Dokumente auswählen",
              e("input", {
                key:
                  "expense-upload-input-" +
                  String(expense.id) +
                  "-" +
                  String(props.expenseUploadInputKey),
                type: "file",
                multiple: true,
                onChange: props.onExpenseDocumentSelection,
                disabled: props.saving || props.loading,
              })
            ),
            e(
              "div",
              { className: "inline-actions" },
              e(
                "button",
                {
                  type: "button",
                  disabled: props.saving || props.loading || uploadFiles.length === 0,
                  onClick: function () {
                    props.onExpenseDocumentUpload(expense.id);
                  },
                },
                props.saving ? "Lädt hoch ..." : "Dokumente hochladen"
              )
            ),
            uploadFiles.length
              ? e(
                  "p",
                  { className: "hint" },
                  String(uploadFiles.length) + " Datei(en) ausgewählt."
                )
              : null,
            table(
              ["Datei", "Status", "Paperless", "Aktion"],
              documents.map(function (document) {
                const openHref =
                  "/api/expenses/" +
                  String(expense.id) +
                  "/documents/" +
                  String(document.id) +
                  "/download";
                return e(
                  "tr",
                  { key: "expense-document-" + String(document.id) },
                  e("td", null, document.filename),
                  e("td", null, document.upload_status),
                  e(
                    "td",
                    null,
                    document.paperless_document_id || document.paperless_task_id || "-"
                  ),
                  e(
                    "td",
                    null,
                    e(
                      "div",
                      { className: "inline-actions" },
                      openHref
                        ? e(
                            "a",
                            {
                              href: openHref,
                              target: "_blank",
                              rel: "noreferrer",
                              className: "action-button secondary",
                            },
                            "Dokument öffnen"
                          )
                        : e("span", null, "Keine Datei"),
                      showDeleteActions
                        ? e(
                            "button",
                            {
                              type: "button",
                              className: "action-button danger",
                              disabled: props.saving || props.loading,
                              onClick: function () {
                                props.onExpenseDocumentDelete(expense.id, document.id);
                              },
                            },
                            "Dokument löschen"
                          )
                        : null
                    )
                  )
                );
              })
            )
          )
        )
      )
    );
  }

  function buildManagementPreview(props) {
    const overview = props.overview || {};
    const managementListFilters = props.managementListFilters || {};
    const selectedMeterId = props.selectedMeterId;
    const editingEntityIds = props.editingEntityIds || {};
    const editingExpenseId = props.editingExpenseId;
    const filteredExpenses = props.filteredExpenses || [];
    const objectActionCell = props.objectActionCell || function () {
      return e("td", null);
    };
    const activeInlineEditorHeading = props.activeInlineEditorHeading || "";
    const activeInlineEditorForm = props.activeInlineEditorForm || null;

    let previewTitle = "Objektliste";
    let previewDescription = "";
    let previewToolbar = null;
    let previewHeaders = [];
    let previewRows = [];

    if (["properties", "buildings", "units", "rooms"].indexOf(props.activeTab) >= 0) {
      const objectEntries = buildHierarchicalObjectEntries(overview);
      previewTitle = "Objektliste";
      previewDescription =
        "Alle Anlagen, Gebäude, Wohnungen und Zimmer in gemeinsamer Hierarchie mit Eltern- und Kindbezug.";
      previewToolbar = buildManagementFilterToolbar({
        title: "Objektliste filtern",
        value: managementListFilters.objects || "",
        placeholder: "Objekttyp, Name, Elternobjekt, Kindobjekte, Details",
        onChange: function (value) {
          props.onManagementFilterChange("objects", value);
        },
      });
      previewHeaders = ["Objekttyp", "Objekt", "Elternobjekt", "Kindobjekte", "Details", "Status", "Aktion"];
      previewRows = [];
      objectEntries
        .filter(function (entry) {
          return matchesManagementFilter(managementListFilters, "objects", [
            entry.typeLabel,
            entry.entity.name,
            entry.entity.label,
            formatObjectParentLabel(entry.tabKey, entry.entity),
            formatObjectChildrenLabel(entry.tabKey, entry.entity),
            formatObjectDetailsLabel(entry.tabKey, entry.entity),
            entry.entity.organization_name,
            entry.entity.property_name,
            entry.entity.building_name,
            entry.entity.unit_label,
          ]);
        })
        .forEach(function (entry) {
          const entity = entry.entity;
          const isEditing = String(editingEntityIds[entry.tabKey] || "") === String(entity.id);
          const editHandler =
            entry.tabKey === "properties"
              ? props.onPropertyEdit
              : entry.tabKey === "buildings"
                ? props.onBuildingEdit
                : entry.tabKey === "units"
                  ? props.onUnitEdit
                  : props.onRoomEdit;
          appendManagementPreviewRow(previewRows, {
            row: e(
              "tr",
              {
                key: entry.tabKey + "-preview-" + String(entity.id),
                className: "selectable-row" + (isEditing ? " selected" : ""),
                onClick: function () {
                  editHandler(entity);
                },
              },
              e("td", null, entry.typeLabel),
              e("td", null, objectHierarchyName(formatDisplayName(entity), entry.level)),
              e("td", null, formatObjectParentLabel(entry.tabKey, entity)),
              e("td", null, formatObjectChildrenLabel(entry.tabKey, entity)),
              e("td", null, formatObjectDetailsLabel(entry.tabKey, entity)),
              e("td", null, objectStatusLabel(entity)),
              objectActionCell(entry.tabKey, entity)
            ),
            isEditing: isEditing,
            inlineRowKey: entry.tabKey + "-preview-edit-" + String(entity.id),
            previewHeadersLength: previewHeaders.length,
            inlineEditorHeading: activeInlineEditorHeading,
            inlineEditorForm: activeInlineEditorForm,
          });
        });
    } else if (props.activeTab === "tenants") {
      previewTitle = "Mieterliste";
      previewDescription = "Alle Mieter mit Kontaktdaten. Per Klick wird die Bearbeitung direkt unterhalb des Eintrags eingeblendet.";
      previewToolbar = buildManagementFilterToolbar({
        title: "Mieterliste filtern",
        value: managementListFilters.tenants || "",
        placeholder: "Name, E-Mail, Telefon",
        onChange: function (value) {
          props.onManagementFilterChange("tenants", value);
        },
      });
      previewHeaders = ["Mieter", "E-Mail", "Telefon"];
      previewRows = [];
      (overview.tenants || [])
        .filter(function (tenant) {
          return matchesManagementFilter(managementListFilters, "tenants", [
            tenant.full_name,
            tenant.email,
            tenant.phone,
          ]);
        })
        .forEach(function (tenant) {
          const isEditing = String(editingEntityIds.tenants) === String(tenant.id);
          appendManagementPreviewRow(previewRows, {
            row: e(
              "tr",
              {
                key: "tenant-preview-" + String(tenant.id),
                className: "selectable-row" + (isEditing ? " selected" : ""),
                onClick: function () {
                  props.onTenantEdit(tenant);
                },
              },
              e("td", null, tenant.full_name),
              e("td", null, tenant.email || "-"),
              e("td", null, tenant.phone || "-")
            ),
            isEditing: isEditing,
            inlineRowKey: "tenant-preview-edit-" + String(tenant.id),
            previewHeadersLength: previewHeaders.length,
            inlineEditorHeading: activeInlineEditorHeading,
            inlineEditorForm: activeInlineEditorForm,
          });
        });
    } else if (props.activeTab === "leases") {
      previewTitle = "Mietvertragsliste";
      previewDescription = "Alle Mietverträge mit Mieter-, Mietobjekt- und Konditionsdaten. Per Klick wird die Bearbeitung direkt unterhalb des Eintrags eingeblendet.";
      previewToolbar = buildManagementFilterToolbar({
        title: "Mietvertragsliste filtern",
        value: managementListFilters.leases || "",
        placeholder: "Mieter, Wohnung, Zimmer, Status, Zeitraum",
        onChange: function (value) {
          props.onManagementFilterChange("leases", value);
        },
      });
      previewHeaders = [
        "Mieter",
        "Mietobjekt",
        "Startdatum",
        "Enddatum",
        "Kaltmiete",
        "Vorauszahlung",
        "Personenzahl",
        "Status",
      ];
      previewRows = [];
      (overview.leases || [])
        .filter(function (lease) {
          return matchesManagementFilter(managementListFilters, "leases", [
            lease.tenant_name,
            lease.rental_object_label,
            lease.unit_label,
            lease.room_label,
            lease.status,
            lease.start_date,
            lease.end_date,
          ]);
        })
        .forEach(function (lease) {
          const isEditing = String(editingEntityIds.leases) === String(lease.id);
          appendManagementPreviewRow(previewRows, {
            row: e(
              "tr",
              {
                key: "lease-preview-" + String(lease.id),
                className: "selectable-row" + (isEditing ? " selected" : ""),
                onClick: function () {
                  props.onLeaseEdit(lease);
                },
              },
              e("td", null, lease.tenant_name || ("ID " + String(lease.tenant_id))),
              e(
                "td",
                null,
                lease.rental_object_label || lease.unit_label || ("ID " + String(lease.unit_id))
              ),
              e("td", null, lease.start_date),
              e("td", null, lease.end_date || "-"),
              e("td", null, String(lease.rent_cold)),
              e("td", null, String(lease.additional_charges_advance)),
              e("td", null, String(lease.occupant_count)),
              e("td", null, lease.status || "-")
            ),
            isEditing: isEditing,
            inlineRowKey: "lease-preview-edit-" + String(lease.id),
            previewHeadersLength: previewHeaders.length,
            inlineEditorHeading: activeInlineEditorHeading,
            inlineEditorForm: activeInlineEditorForm,
          });
        });
    } else if (props.activeTab === "meters") {
      previewTitle = "Objektliste Zähler";
      previewDescription = "Alle Zähler mit Objektzuordnung, letztem Zählerstand, Archivstatus und Lifecycle-Aktion.";
      previewHeaders = [
        "Zähler",
        "Zielobjektart",
        "Zielobjekt",
        "Anlage",
        "Einheit",
        "Letzter Zählerstand",
        "Ablesedatum",
        "Anzahl Zählerstände",
        "Status",
        "Aktion",
      ];
      previewRows = [];
      (overview.meters || []).forEach(function (meter) {
        const isEditing = String(editingEntityIds.meters || "") === String(meter.id);
        appendManagementPreviewRow(previewRows, {
          row: e(
            "tr",
            {
              key: "meter-preview-" + String(meter.id),
              className:
                "selectable-row" + (String(selectedMeterId) === String(meter.id) ? " selected" : ""),
              onClick: function () {
                props.onMeterSelect(meter.id);
              },
            },
          e("td", null, formatDisplayName(meter)),
          e("td", null, formatObjectTypeLabel(meter.object_type)),
          e("td", null, meter.object_name || ("ID " + String(meter.object_id))),
          e("td", null, meter.property_name || "Keine Anlage"),
          e("td", null, meter.unit),
          e("td", null, meter.latest_reading_value == null ? "-" : String(meter.latest_reading_value)),
          e("td", null, meter.latest_reading_date || "-"),
          e("td", null, String(meter.reading_count || 0)),
          e("td", null, objectStatusLabel(meter)),
            props.meterActionCell
            ? props.meterActionCell(meter)
            : objectActionCell("meters", meter)
          ),
          isEditing: isEditing,
          inlineRowKey: "meter-preview-edit-" + String(meter.id),
          previewHeadersLength: previewHeaders.length,
          inlineEditorHeading: activeInlineEditorHeading,
          inlineEditorForm: activeInlineEditorForm,
        });
      });
    } else {
      previewTitle = "Kostenliste";
      previewDescription =
        "Alle bereits angelegten Kosten. Aktive Kosten können per Klick auf die Zeile inline bearbeitet werden.";
      previewToolbar = buildExpenseFilterToolbar({
        filters: props.expenseListFilters,
        expenseListTargetOptions: props.expenseListTargetOptions,
        expenseCategoryFilterOptions: props.expenseCategoryFilterOptions,
        onChange: props.onExpenseListFilterChange,
      });
      previewHeaders = [
        "Kostenart",
        "Bezeichnung",
        "Empfänger",
        "Zielobjekt",
        "Abrechnungsart",
        "Turnus",
        "Wert (EUR)",
        "Gesamtsumme (EUR)",
        "Datum oder Zeitraum",
        "Zähler",
        "Verbrauchseinheit",
        "Status",
        "Aktion",
      ];
      previewRows = [];
      filteredExpenses.slice().sort(sortExpensesByEndDateDesc).forEach(function (expense) {
        previewRows.push(
          e(
            "tr",
            {
              key: "expense-preview-" + String(expense.id),
              className:
                !expense.is_archived
                  ? "selectable-row" +
                    (String(editingExpenseId) === String(expense.id) ? " selected" : "")
                  : "",
              onClick: !expense.is_archived
                ? function () {
                    props.onExpenseEdit(expense);
                  }
                : null,
            },
            e("td", null, formatExpenseCategoryLabel(expense)),
            e("td", null, expense.label || "-"),
            e("td", null, expense.beneficiary_name || "Nicht gepflegt"),
            e("td", null, formatExpenseTargetLabel(expense)),
            e("td", null, formatExpenseBillingType(expense)),
            e("td", null, formatExpenseCadence(expense)),
            e("td", null, formatExpenseAmountValue(expense)),
            e("td", null, expense.total_amount == null ? "-" : expense.total_amount),
            e("td", null, formatExpenseWindow(expense)),
            e("td", null, expense.meter_label || "-"),
            e("td", null, expense.consumption_unit || "-"),
            e("td", null, objectStatusLabel(expense)),
            objectActionCell("expenses", expense)
          )
        );

        if (String(editingExpenseId) === String(expense.id) && !expense.is_archived) {
          previewRows.push(
            buildExpenseInlineEditor({
              expense: expense,
              previewHeadersLength: previewHeaders.length,
              expenseEditForm: props.expenseEditForm,
              onExpenseUpdateSubmit: props.onExpenseUpdateSubmit,
              onExpenseEditFieldChange: props.onExpenseEditFieldChange,
              onExpenseEditCategoryChange: props.onExpenseEditCategoryChange,
              onExpenseEditTargetChange: props.onExpenseEditTargetChange,
              onExpenseEditMeterChange: props.onExpenseEditMeterChange,
              onExpenseArchive: props.onExpenseArchive,
              onExpenseEditCancel: props.onExpenseEditCancel,
              overview: overview,
              expenseTargetOptions: props.expenseTargetOptions,
              expenseCategorySuggestions: props.expenseCategorySuggestions,
              meterOptions: props.expenseEditMeterOptions,
              calculateMeterConsumptionValue: props.calculateMeterConsumptionValue,
              saving: props.saving,
              loading: props.loading,
              expenseDocuments: props.expenseDocuments,
              expenseUploadFiles: props.expenseUploadFiles,
              expenseDocumentReferenceId: props.expenseDocumentReferenceId,
              expenseUploadInputKey: props.expenseUploadInputKey,
              onExpenseDocumentSelection: props.onExpenseDocumentSelection,
              onExpenseDocumentReferenceIdChange: props.onExpenseDocumentReferenceIdChange,
              onExpenseDocumentReferenceCreate: props.onExpenseDocumentReferenceCreate,
              onExpenseDocumentUpload: props.onExpenseDocumentUpload,
              onExpenseDocumentDelete: props.onExpenseDocumentDelete,
              showDeleteActions: props.showDeleteActions,
            })
          );
        }
      });
    }

    return {
      previewTitle: previewTitle,
      previewDescription: previewDescription,
      previewToolbar: previewToolbar,
      previewHeaders: previewHeaders,
      previewRows: previewRows,
    };
  }

  window.EasyPrentAppPreviews = {
    buildFilteredExpenses: buildFilteredExpenses,
    expenseOverlapsYear: expenseOverlapsYear,
    buildManagementPreview: buildManagementPreview,
    buildMeterData: buildMeterData,
    buildOverviewRows: buildOverviewRows,
  };
})();
