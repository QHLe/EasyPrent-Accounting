(function () {
  if (!window.React) {
    return;
  }

  const e = React.createElement;
  const domain = window.EasyPrentAppDomain || {};
  const buildObjectTargetValue = domain.buildObjectTargetValue;
  const formatMoneyValue = domain.formatMoneyValue;
  const table =
    domain.table ||
    function (headers, rows) {
      return e(
        "table",
        null,
        e(
          "thead",
          null,
          e(
            "tr",
            null,
            headers.map(function (header) {
              return e("th", { key: header }, header);
            })
          )
        ),
        e(
          "tbody",
          null,
          rows.length
            ? rows
            : e(
                "tr",
                null,
                e("td", { colSpan: headers.length }, "Keine Daten vorhanden.")
              )
        )
      );
    };

  function renderLinkedDocumentSection(props) {
    const documents = props.documents || [];
    const uploadFiles = props.uploadFiles || [];
    const normalizedDocumentReferenceId = String(props.documentReferenceId || "").trim();
    const showDeleteActions = props.showDeleteActions !== false;

    return e(
      "div",
      { className: "stack" },
      e("h4", null, props.heading),
      props.hint ? e("p", { className: "hint" }, props.hint) : null,
      e(
        "label",
        null,
        "Paperless Dokument-ID",
        e("input", {
          type: "text",
          value: props.documentReferenceId || "",
          placeholder: "4711",
          onChange: function (event) {
            props.onDocumentReferenceIdChange(event.target.value);
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
              normalizedDocumentReferenceId === "",
            onClick: function () {
              props.onDocumentReferenceCreate(props.resourcePlural, props.resourceId);
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
            "management-upload-input-" +
            String(props.resourcePlural) +
            "-" +
            String(props.resourceId) +
            "-" +
            String(props.uploadInputKey),
          type: "file",
          multiple: true,
          onChange: props.onDocumentSelection,
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
              props.onDocumentUpload(props.resourcePlural, props.resourceId);
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
            "/api/" +
            String(props.resourcePlural) +
            "/" +
            String(props.resourceId) +
            "/documents/" +
            String(document.id) +
            "/download";
          return e(
            "tr",
            { key: String(props.resourcePlural) + "-document-" + String(document.id) },
            e("td", null, document.filename),
            e("td", null, document.upload_status),
            e("td", null, document.paperless_document_id || document.paperless_task_id || "-"),
            e(
              "td",
              null,
              e(
                "div",
                { className: "inline-actions" },
                e(
                  "a",
                  {
                    href: openHref,
                    target: "_blank",
                    rel: "noreferrer",
                    className: "action-button secondary",
                  },
                  "Dokument öffnen"
                ),
                showDeleteActions
                  ? e(
                      "button",
                      {
                        type: "button",
                        className: "action-button danger",
                        disabled: props.saving || props.loading,
                        onClick: function () {
                          props.onDocumentDelete(props.resourcePlural, props.resourceId, document.id);
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
    );
  }

  function renderExpenseForm(props) {
    const formState = props.formState;
    const overview = props.overview || {};
    const selectedMeter = ((overview && overview.meters) || []).find(function (meter) {
      return String(meter.id) === String(formState.meter_id);
    });
    const showManualConsumptionValue =
      formState.charge_type === "consumption" && !formState.meter_id;
    const showConversionFactor =
      formState.charge_type === "consumption" &&
      !!formState.meter_id &&
      selectedMeter &&
      formState.consumption_unit !== "" &&
      formState.consumption_unit !== selectedMeter.unit;
    const latestMeterReading = selectedMeter
      ? ((overview && overview.meter_readings) || [])
          .filter(function (reading) {
            return String(reading.meter_id) === String(selectedMeter.id);
          })
          .sort(function (left, right) {
            return String(right.reading_date).localeCompare(String(left.reading_date));
          })[0] || null
      : null;
    const effectiveMeterPeriodEnd =
      formState.period_end || (latestMeterReading ? latestMeterReading.reading_date : "");
    const meterConsumptionValue =
      selectedMeter && formState.period_start && effectiveMeterPeriodEnd
        ? props.calculateMeterConsumptionValue(
            formState.meter_id,
            formState.period_start,
            effectiveMeterPeriodEnd,
            overview
          )
        : null;
    const convertedMeterConsumptionValue =
      meterConsumptionValue !== null
        ? meterConsumptionValue *
          Number(
            showConversionFactor && formState.conversion_factor !== ""
              ? formState.conversion_factor
              : "1"
          )
        : null;
    const formTotalAmount =
      formState.charge_type === "consumption"
        ? selectedMeter && convertedMeterConsumptionValue !== null && formState.amount !== ""
          ? formatMoneyValue(Number(formState.amount) * convertedMeterConsumptionValue)
          : selectedMeter && formState.total_amount != null
            ? formState.total_amount
            : !formState.meter_id &&
                formState.amount !== "" &&
                formState.consumption_value !== ""
              ? formatMoneyValue(Number(formState.amount) * Number(formState.consumption_value))
              : "-"
        : "-";
    return e(
      "form",
      { onSubmit: props.onSubmit },
      e(
        "div",
        { className: "form-grid" },
        e(
          "label",
          null,
          "Zielobjekt",
          e(
            "select",
            {
              value: buildObjectTargetValue(formState.object_type, formState.object_id),
              onChange: function (event) {
                props.setTargetValue(event.target.value);
              },
              required: true,
            },
            e("option", { value: "" }, "Objekt wählen"),
            props.expenseTargetOptions
          )
        ),
        e(
          "label",
          null,
          "Kostenart",
          e("input", {
            value: formState.expense_category,
            list: "expense-category-suggestions",
            onChange: function (event) {
              props.setExpenseCategory(event.target.value);
            },
            required: true,
          }),
          e("datalist", { id: "expense-category-suggestions" }, props.expenseCategorySuggestions)
        ),
        e(
          "label",
          null,
          "Bezeichnung",
          e("input", {
            value: formState.label,
            onChange: function (event) {
              props.setField("label", event.target.value);
            },
            required: true,
          })
        ),
        e(
          "label",
          null,
          "Empfänger",
          e("input", {
            value: formState.beneficiary_name,
            onChange: function (event) {
              props.setField("beneficiary_name", event.target.value);
            },
            required: true,
          })
        ),
        e(
          "label",
          null,
          "Wert (EUR)",
          e("input", {
            type: "number",
            step: "0.0000000001",
            min: "0",
            value: formState.amount,
            onChange: function (event) {
              props.setField("amount", event.target.value);
            },
            required: true,
          })
        ),
        formState.charge_type === "consumption"
          ? e("p", { className: "hint" }, "Wert wird als Preis je Einheit verwendet.")
          : null,
        e(
          "label",
          null,
          "Verteilerschlüssel",
          e(
            "select",
            {
              value: formState.allocation_method,
              onChange: function (event) {
                props.setField("allocation_method", event.target.value);
              },
            },
            e("option", { value: "area" }, "Nach Fläche"),
            e("option", { value: "unit_count" }, "Nach Einheiten"),
            e("option", { value: "occupants" }, "Nach Personen")
          )
        ),
        e(
          "label",
          null,
          "Abrechnungsart",
          e(
            "select",
            {
              value: formState.charge_type,
              onChange: function (event) {
                props.setField("charge_type", event.target.value);
              },
            },
            e("option", { value: "one_time" }, "Gesamtkosten"),
            e("option", { value: "recurring" }, "Wiederholend"),
            e("option", { value: "consumption" }, "Verbrauchsbezogen")
          )
        ),
        formState.charge_type === "recurring"
          ? e(
              "label",
              null,
              "Intervall",
              e(
                "select",
                {
                  value: formState.interval,
                  onChange: function (event) {
                    props.setField("interval", event.target.value);
                  },
                },
                e("option", { value: "monthly" }, "Monatlich"),
                e("option", { value: "quarterly" }, "Vierteljährlich"),
                e("option", { value: "yearly" }, "Jährlich")
              )
            )
          : null,
        e(
          "label",
          null,
          "Von Datum",
          e("input", {
            type: "date",
            value: formState.period_start,
            onChange: function (event) {
              props.setField("period_start", event.target.value);
            },
            required: true,
          })
        ),
        e(
          "label",
          null,
          (formState.charge_type === "consumption" && selectedMeter) ||
            formState.charge_type === "recurring"
            ? "Bis Datum (optional)"
            : "Bis Datum",
          e("input", {
            type: "date",
            value: formState.period_end,
            onChange: function (event) {
              props.setField("period_end", event.target.value);
            },
            required: !(
              (formState.charge_type === "consumption" && selectedMeter) ||
              formState.charge_type === "recurring"
            ),
          })
        ),
        formState.charge_type === "consumption"
          ? e(
              "label",
              null,
              "Zähler optional",
              e(
                "select",
                {
                  value: formState.meter_id,
                  onChange: function (event) {
                    props.setMeterId(event.target.value);
                  },
                },
                e("option", { value: "" }, "Ohne Zähler"),
                props.meterOptions
              )
            )
          : null,
        formState.charge_type === "consumption" && selectedMeter && latestMeterReading
          ? e(
              "p",
              { className: "hint" },
              "Ohne Enddatum wird bis zum letzten Zählerstand am ",
              latestMeterReading.reading_date,
              " berechnet."
            )
          : null,
        formState.charge_type === "consumption"
          ? e(
              "label",
              null,
              "Verbrauchseinheit",
              e("input", {
                value: formState.consumption_unit,
                onChange: function (event) {
                  props.setField("consumption_unit", event.target.value);
                },
              })
            )
          : null,
        showManualConsumptionValue
          ? e(
              "label",
              null,
              "Verbrauchswert",
              e("input", {
                type: "number",
                step: "0.01",
                min: "0",
                value: formState.consumption_value,
                onChange: function (event) {
                  props.setField("consumption_value", event.target.value);
                },
              })
            )
          : null,
        showConversionFactor
          ? e(
              "label",
              null,
              "Umrechnungsfaktor",
              e("input", {
                type: "number",
                step: "0.0001",
                min: "0.0001",
                value: formState.conversion_factor,
                onChange: function (event) {
                  props.setField("conversion_factor", event.target.value);
                },
                required: true,
              })
            )
          : null,
        formState.charge_type === "consumption"
          ? e(
              "p",
              { className: "hint" },
              "Gesamtsumme: ",
              formTotalAmount + " EUR",
              selectedMeter
                ? " | Zähleinheit: " +
                  selectedMeter.unit +
                  (convertedMeterConsumptionValue !== null
                    ? " | Abgerechnete Menge: " +
                      String(Number(convertedMeterConsumptionValue.toFixed(4)))
                    : "")
                : ""
            )
          : null,
        e(
          "div",
          { className: "inline-actions" },
          e(
            "button",
            { type: "submit", disabled: props.saving || props.loading },
            props.saving ? "Speichert ..." : props.submitLabel
          ),
          props.extraAction
        )
      )
    );
  }

  function renderManagementActiveForm(props) {
    const activeTab = props.activeTab;
    const editingEntityIds = props.editingEntityIds || {};
    const forms = props.forms || {};
    const handleCancelEdit =
      typeof props.cancelManagementEdit === "function"
        ? props.cancelManagementEdit
        : props.clearEditingForTab;
    let activeHeading = "";
    let activeForm = null;

    if (activeTab === "properties") {
      const isEditing = String(editingEntityIds.properties || "") !== "";
      activeHeading = isEditing ? "Anlage bearbeiten" : "Anlage erfassen";
      activeForm = e(
        "form",
        { onSubmit: props.handlePropertySubmit },
        e(
          "div",
          { className: "form-grid" },
          e(
            "label",
            null,
            "Anlagenname",
            e("input", {
              name: "name",
              value: forms.property.name,
              onChange: function (event) {
                props.setFormField("property", "name", event.target.value);
              },
              required: true,
            })
          ),
          e(
            "label",
            null,
            "Straße",
            e("input", {
              name: "street",
              value: forms.property.street,
              onChange: function (event) {
                props.setFormField("property", "street", event.target.value);
              },
              required: true,
            })
          ),
          e(
            "label",
            null,
            "Ort",
            e("input", {
              name: "city",
              value: forms.property.city,
              onChange: function (event) {
                props.setFormField("property", "city", event.target.value);
              },
              required: true,
            })
          ),
          e(
            "label",
            null,
            "Postleitzahl",
            e("input", {
              name: "postal_code",
              value: forms.property.postal_code,
              onChange: function (event) {
                props.setFormField("property", "postal_code", event.target.value);
              },
              required: true,
            })
          ),
          e(
            "div",
            { className: "inline-actions" },
            e(
              "button",
              { type: "submit", disabled: props.saving || props.loading },
              props.saving ? "Speichert ..." : isEditing ? "Anlage aktualisieren" : "Anlage speichern"
            ),
            isEditing
              ? e(
                  "button",
                  {
                    type: "button",
                    className: "action-button secondary",
                    disabled: props.saving || props.loading,
                    onClick: function () {
                      handleCancelEdit("properties");
                    },
                  },
                  "Bearbeitung abbrechen"
                )
              : null
          )
        )
      );
    } else if (activeTab === "buildings") {
      const isEditing = String(editingEntityIds.buildings || "") !== "";
      activeHeading = isEditing ? "Gebäude bearbeiten" : "Gebäude erfassen";
      activeForm = e(
        "form",
        { onSubmit: props.handleBuildingSubmit },
        e(
          "div",
          { className: "form-grid" },
          e(
            "label",
            null,
            "Anlage",
            e(
              "select",
              {
                value: forms.building.property_id,
                onChange: function (event) {
                  props.setFormField("building", "property_id", event.target.value);
                },
              },
              e("option", { value: "" }, "Ohne Anlage"),
              props.propertyOptions
            )
          ),
          e(
            "label",
            null,
            "Gebäudename",
            e("input", {
              value: forms.building.name,
              onChange: function (event) {
                props.setFormField("building", "name", event.target.value);
              },
              required: true,
            })
          ),
          e(
            "label",
            null,
            "Baujahr",
            e("input", {
              type: "number",
              value: forms.building.year_built,
              onChange: function (event) {
                props.setFormField("building", "year_built", event.target.value);
              },
            })
          ),
          e(
            "label",
            null,
            "Gebäude-Straße",
            e("input", {
              value: forms.building.street,
              onChange: function (event) {
                props.setFormField("building", "street", event.target.value);
              },
              required: true,
            })
          ),
          e(
            "label",
            null,
            "Gebäude-Ort",
            e("input", {
              value: forms.building.city,
              onChange: function (event) {
                props.setFormField("building", "city", event.target.value);
              },
              required: true,
            })
          ),
          e(
            "label",
            null,
            "Gebäude-Postleitzahl",
            e("input", {
              value: forms.building.postal_code,
              onChange: function (event) {
                props.setFormField("building", "postal_code", event.target.value);
              },
              required: true,
            })
          ),
          e(
            "div",
            { className: "inline-actions" },
            e(
              "button",
              { type: "submit", disabled: props.saving || props.loading },
              props.saving ? "Speichert ..." : isEditing ? "Gebäude aktualisieren" : "Gebäude speichern"
            ),
            isEditing
              ? e(
                  "button",
                  {
                    type: "button",
                    className: "action-button secondary",
                    disabled: props.saving || props.loading,
                    onClick: function () {
                      handleCancelEdit("buildings");
                    },
                  },
                  "Bearbeitung abbrechen"
                )
              : null
          )
        )
      );
    } else if (activeTab === "units") {
      const isEditing = String(editingEntityIds.units || "") !== "";
      activeHeading = isEditing ? "Wohnung bearbeiten" : "Wohnung erfassen";
      activeForm = e(
        "form",
        { onSubmit: props.handleUnitSubmit },
        e(
          "div",
          { className: "form-grid" },
          e(
            "label",
            null,
            "Gebäude",
            e(
              "select",
              {
                value: forms.unit.building_id,
                onChange: function (event) {
                  props.setUnitBuildingId(event.target.value);
                },
              },
              e("option", { value: "" }, "Ohne Gebäude"),
              props.buildingOptions
            )
          ),
          e(
            "label",
            null,
            "Wohnungsbezeichnung",
            e("input", {
              value: forms.unit.label,
              onChange: function (event) {
                props.setFormField("unit", "label", event.target.value);
              },
              required: true,
            })
          ),
          e(
            "label",
            null,
            "Fläche in m²",
            e("input", {
              type: "number",
              step: "0.1",
              value: forms.unit.area_sqm,
              onChange: function (event) {
                props.setFormField("unit", "area_sqm", event.target.value);
              },
              required: true,
            })
          ),
          e(
            "label",
            null,
            "Zimmeranzahl",
            e("input", {
              type: "number",
              min: "1",
              value: forms.unit.room_count,
              onChange: function (event) {
                props.setFormField("unit", "room_count", event.target.value);
              },
              required: true,
            })
          ),
          e(
            "label",
            null,
            "Wohnungs-Straße",
            e("input", {
              value: forms.unit.street,
              onChange: function (event) {
                props.setFormField("unit", "street", event.target.value);
              },
              required: true,
              readOnly: forms.unit.building_id !== "",
            })
          ),
          e(
            "label",
            null,
            "Wohnungs-Ort",
            e("input", {
              value: forms.unit.city,
              onChange: function (event) {
                props.setFormField("unit", "city", event.target.value);
              },
              required: true,
              readOnly: forms.unit.building_id !== "",
            })
          ),
          e(
            "label",
            null,
            "Wohnungs-Postleitzahl",
            e("input", {
              value: forms.unit.postal_code,
              onChange: function (event) {
                props.setFormField("unit", "postal_code", event.target.value);
              },
              required: true,
              readOnly: forms.unit.building_id !== "",
            })
          ),
          e(
            "div",
            { className: "inline-actions" },
            e(
              "button",
              { type: "submit", disabled: props.saving || props.loading },
              props.saving ? "Speichert ..." : isEditing ? "Wohnung aktualisieren" : "Wohnung speichern"
            ),
            isEditing
              ? e(
                  "button",
                  {
                    type: "button",
                    className: "action-button secondary",
                    disabled: props.saving || props.loading,
                    onClick: function () {
                      handleCancelEdit("units");
                    },
                  },
                  "Bearbeitung abbrechen"
                )
              : null
          )
        )
      );
    } else if (activeTab === "rooms") {
      const isEditing = String(editingEntityIds.rooms || "") !== "";
      activeHeading = isEditing ? "Zimmer bearbeiten" : "Zimmer erfassen";
      activeForm = e(
        "form",
        { onSubmit: props.handleRoomSubmit },
        e(
          "div",
          { className: "form-grid" },
          e(
            "label",
            null,
            "Wohnung",
            e(
              "select",
              {
                value: forms.room.unit_id,
                onChange: function (event) {
                  props.setFormField("room", "unit_id", event.target.value);
                },
                required: true,
              },
              e("option", { value: "" }, "Wohnung wählen"),
              props.unitOptions
            )
          ),
          e(
            "label",
            null,
            "Zimmername",
            e("input", {
              value: forms.room.label,
              onChange: function (event) {
                props.setFormField("room", "label", event.target.value);
              },
              required: true,
            })
          ),
          e(
            "label",
            null,
            "Zimmerfläche in m²",
            e("input", {
              type: "number",
              min: "0",
              step: "0.01",
              value: forms.room.area_sqm,
              onChange: function (event) {
                props.setFormField("room", "area_sqm", event.target.value);
              },
            })
          ),
          e(
            "div",
            { className: "inline-actions" },
            e(
              "button",
              { type: "submit", disabled: props.saving || props.loading },
              props.saving ? "Speichert ..." : isEditing ? "Zimmer aktualisieren" : "Zimmer speichern"
            ),
            isEditing
              ? e(
                  "button",
                  {
                    type: "button",
                    className: "action-button secondary",
                    disabled: props.saving || props.loading,
                    onClick: function () {
                      handleCancelEdit("rooms");
                    },
                  },
                  "Bearbeitung abbrechen"
                )
              : null
          )
        )
      );
    } else if (activeTab === "tenants") {
      const isEditing = String(editingEntityIds.tenants || "") !== "";
      const editingTenantId = editingEntityIds.tenants || "";
      activeHeading = isEditing ? "Mieter bearbeiten" : "Mieter erfassen";
      activeForm = e(
        "form",
        { onSubmit: props.handleTenantSubmit },
        e(
          React.Fragment,
          null,
          e(
            "div",
            { className: "form-grid" },
            e(
              "label",
              null,
              "Mietername",
              e("input", {
                value: forms.tenant.full_name,
                onChange: function (event) {
                  props.setFormField("tenant", "full_name", event.target.value);
                },
                required: true,
              })
            ),
            e(
              "label",
              null,
              "E-Mail optional",
              e("input", {
                type: "email",
                value: forms.tenant.email,
                onChange: function (event) {
                  props.setFormField("tenant", "email", event.target.value);
                },
              })
            ),
            e(
              "label",
              null,
              "Telefon optional",
              e("input", {
                value: forms.tenant.phone,
                onChange: function (event) {
                  props.setFormField("tenant", "phone", event.target.value);
                },
              })
            ),
            e("label", null, "Abweichende Straße optional", e("input", { value: forms.tenant.alternate_street, onChange: function (event) { props.setFormField("tenant", "alternate_street", event.target.value); } })),
            e("label", null, "Abweichende PLZ optional", e("input", { value: forms.tenant.alternate_postal_code, onChange: function (event) { props.setFormField("tenant", "alternate_postal_code", event.target.value); } })),
            e("label", null, "Abweichender Ort optional", e("input", { value: forms.tenant.alternate_city, onChange: function (event) { props.setFormField("tenant", "alternate_city", event.target.value); } })),
            e(
              "label",
              null,
              "GnuCash-NK-Vorauszahlungskonto optional",
              e(
                "select",
                {
                  value: forms.tenant.gnucash_nk_account_guid || "",
                  onChange: function (event) {
                    const account = (props.gnucashAccounts || []).find(function (candidate) {
                      return candidate.guid === event.target.value;
                    });
                    props.setFormField("tenant", "gnucash_nk_account_guid", event.target.value);
                    props.setFormField(
                      "tenant",
                      "gnucash_nk_account_name",
                      account ? account.full_name : ""
                    );
                  },
                },
                (function () {
                  const accounts = props.gnucashAccounts || [];
                  const linkedAccountGuid = forms.tenant.gnucash_nk_account_guid || "";
                  const isLinkedAccountLoaded = accounts.some(function (account) {
                    return account.guid === linkedAccountGuid;
                  });
                  const linkedAccountOption =
                    linkedAccountGuid && !isLinkedAccountLoaded
                      ? [
                          e(
                            "option",
                            { key: linkedAccountGuid, value: linkedAccountGuid },
                            forms.tenant.gnucash_nk_account_name || "Verknüpftes GnuCash-Konto"
                          ),
                        ]
                      : [];
                  return linkedAccountOption.concat(
                    accounts.map(function (account) {
                      return e("option", { key: account.guid, value: account.guid }, account.full_name);
                    })
                  );
                })()
              )
            ),
            e(
              "div",
              { className: "inline-actions" },
              e(
                "button",
                {
                  type: "button",
                  className: "action-button secondary",
                  disabled: props.saving || props.loading || typeof props.onLoadGnuCashAccounts !== "function",
                  onClick: props.onLoadGnuCashAccounts,
                },
                "GnuCash-Konten laden"
              ),
            ),
            e(
              "div",
              { className: "inline-actions" },
              e(
                "button",
                { type: "submit", disabled: props.saving || props.loading },
                props.saving ? "Speichert ..." : isEditing ? "Mieter aktualisieren" : "Mieter speichern"
              ),
              isEditing &&
              props.showDeleteActions &&
              typeof props.onTenantDelete === "function"
                ? e(
                    "button",
                    {
                      type: "button",
                      className: "action-button danger",
                      disabled: props.saving || props.loading,
                      onClick: function () {
                        props.onTenantDelete(editingEntityIds.tenants || "");
                      },
                    },
                    "Mieter löschen"
                  )
                : null,
              isEditing
                ? e(
                    "button",
                    {
                      type: "button",
                      className: "action-button secondary",
                      disabled: props.saving || props.loading,
                      onClick: function () {
                        handleCancelEdit("tenants");
                      },
                    },
                    "Bearbeitung abbrechen"
                  )
                : null
            )
          ),
          isEditing
            ? renderLinkedDocumentSection({
                heading: "Identitätsdokumente",
                hint:
                  "Reisepass, Personalausweis und weitere Unterlagen können hier direkt hochgeladen oder per Paperless-Dokument-ID verknüpft werden.",
                resourcePlural: "tenants",
                resourceId: editingTenantId,
                documents: props.managementDocuments,
                uploadFiles: props.managementUploadFiles,
                documentReferenceId: props.managementDocumentReferenceId,
                uploadInputKey: props.managementUploadInputKey,
                onDocumentSelection: props.onManagementDocumentSelection,
                onDocumentReferenceIdChange: props.onManagementDocumentReferenceIdChange,
                onDocumentReferenceCreate: props.onManagementDocumentReferenceCreate,
                onDocumentUpload: props.onManagementDocumentUpload,
                onDocumentDelete: props.onManagementDocumentDelete,
                showDeleteActions: props.showDeleteActions,
                saving: props.saving,
                loading: props.loading,
              })
            : null
        )
      );
    } else if (activeTab === "leases") {
      const isEditing = String(editingEntityIds.leases || "") !== "";
      const editingLeaseId = editingEntityIds.leases || "";
      activeHeading = isEditing ? "Mietvertrag bearbeiten" : "Mietvertrag erfassen";
      activeForm = e(
        "form",
        { onSubmit: props.handleLeaseSubmit },
        e(
          React.Fragment,
          null,
          e(
            "div",
            { className: "form-grid" },
          e(
            "label",
            null,
            "Mieter",
            e(
              "select",
              {
                value: forms.lease.tenant_id,
                onChange: function (event) {
                  props.setFormField("lease", "tenant_id", event.target.value);
                },
                required: true,
              },
              e("option", { value: "" }, "Mieter wählen"),
              props.tenantOptions
            )
          ),
          e(
            "label",
            null,
            "Wohnung",
            e(
              "select",
              {
                value: forms.lease.unit_id,
                onChange: function (event) {
                  if (typeof props.setLeaseUnitId === "function") {
                    props.setLeaseUnitId(event.target.value);
                    return;
                  }
                  props.setFormField("lease", "unit_id", event.target.value);
                },
                required: true,
              },
              e("option", { value: "" }, "Wohnung wählen"),
              props.unitOptions
            )
          ),
          e(
            "label",
            null,
            "Zimmer optional",
            e(
              "select",
              {
                value: forms.lease.room_id || "",
                onChange: function (event) {
                  if (typeof props.setLeaseRoomId === "function") {
                    props.setLeaseRoomId(event.target.value);
                    return;
                  }
                  props.setFormField("lease", "room_id", event.target.value);
                },
              },
              e("option", { value: "" }, "Kein Zimmer"),
              props.leaseRoomOptions
            )
          ),
          e(
            "label",
            null,
            "Kaltmiete",
            e("input", {
              type: "number",
              step: "0.01",
              min: "0",
              value: forms.lease.rent_cold,
              onChange: function (event) {
                props.setFormField("lease", "rent_cold", event.target.value);
              },
              required: true,
            })
          ),
          e(
            "label",
            null,
            "Nebenkostenvorauszahlung pro Monat",
            e("input", {
              type: "number",
              step: "0.01",
              min: "0",
              value: forms.lease.additional_charges_advance,
              onChange: function (event) {
                props.setFormField("lease", "additional_charges_advance", event.target.value);
              },
              required: true,
            })
          ),
          e(
            "label",
            null,
            "Personenzahl",
            e("input", {
              type: "number",
              min: "1",
              value: forms.lease.occupant_count,
              onChange: function (event) {
                props.setFormField("lease", "occupant_count", event.target.value);
              },
              required: true,
            })
          ),
          e(
            "label",
            null,
            "Startdatum",
            e("input", {
              type: "date",
              value: forms.lease.start_date,
              onChange: function (event) {
                props.setFormField("lease", "start_date", event.target.value);
              },
              required: true,
            })
          ),
          e(
            "label",
            null,
            "Enddatum optional",
            e("input", {
              type: "date",
              value: forms.lease.end_date,
              onChange: function (event) {
                props.setFormField("lease", "end_date", event.target.value);
              },
            })
          ),
          e(
            "label",
            null,
            "Status",
            e(
              "select",
              {
                value: forms.lease.status,
                onChange: function (event) {
                  props.setFormField("lease", "status", event.target.value);
                },
              },
              e("option", { value: "active" }, "Aktiv"),
              e("option", { value: "ended" }, "Beendet")
            )
          ),
          e(
            "div",
            { className: "inline-actions" },
            e(
              "button",
              { type: "submit", disabled: props.saving || props.loading },
              props.saving
                ? "Speichert ..."
                : isEditing
                  ? "Mietvertrag aktualisieren"
                  : "Mietvertrag speichern"
            ),
            isEditing &&
            props.showDeleteActions &&
            typeof props.onLeaseDelete === "function"
              ? e(
                  "button",
                  {
                    type: "button",
                    className: "action-button danger",
                    disabled: props.saving || props.loading,
                    onClick: function () {
                      props.onLeaseDelete(editingEntityIds.leases || "");
                    },
                  },
                  "Mietvertrag löschen"
                )
              : null,
            isEditing
              ? e(
                  "button",
                  {
                    type: "button",
                    className: "action-button secondary",
                    disabled: props.saving || props.loading,
                    onClick: function () {
                      handleCancelEdit("leases");
                    },
                  },
                  "Bearbeitung abbrechen"
                )
              : null
          )
          ),
          isEditing
            ? renderLinkedDocumentSection({
                heading: "Vertragsdokumente",
                hint:
                  "Vertragsunterlagen können hier direkt hochgeladen oder per Paperless-Dokument-ID mit dem Mietvertrag verknüpft werden.",
                resourcePlural: "leases",
                resourceId: editingLeaseId,
                documents: props.managementDocuments,
                uploadFiles: props.managementUploadFiles,
                documentReferenceId: props.managementDocumentReferenceId,
                uploadInputKey: props.managementUploadInputKey,
                onDocumentSelection: props.onManagementDocumentSelection,
                onDocumentReferenceIdChange: props.onManagementDocumentReferenceIdChange,
                onDocumentReferenceCreate: props.onManagementDocumentReferenceCreate,
                onDocumentUpload: props.onManagementDocumentUpload,
                onDocumentDelete: props.onManagementDocumentDelete,
                showDeleteActions: props.showDeleteActions,
                saving: props.saving,
                loading: props.loading,
              })
            : null
        )
      );
    } else if (activeTab === "meters") {
      const isEditing = String(editingEntityIds.meters || "") !== "";
      activeHeading = isEditing ? "Zähler bearbeiten" : "Zähler und Zählerstände erfassen";
      activeForm = e(
        "div",
        { className: "stack" },
        e(
          "form",
          { onSubmit: props.handleMeterSubmit },
          e(
            "div",
            { className: "form-grid" },
            e(
              "label",
              null,
              "Zielobjektart",
              e(
                "select",
                {
                  value: forms.meter.object_type,
                  onChange: function (event) {
                    props.setMeterObjectType(event.target.value);
                  },
                  required: true,
                },
                e("option", { value: "property" }, "Anlage"),
                e("option", { value: "building" }, "Gebäude"),
                e("option", { value: "unit" }, "Wohnung"),
                e("option", { value: "room" }, "Zimmer")
              )
            ),
            e(
              "label",
              null,
              "Zielobjekt",
              e(
                "select",
                {
                  value: forms.meter.object_id,
                  onChange: function (event) {
                    props.setFormField("meter", "object_id", event.target.value);
                  },
                  required: true,
                },
                e("option", { value: "" }, "Objekt wählen"),
                props.meterTargetOptions
              )
            ),
            e(
              "label",
              null,
              "Zählername",
              e("input", {
                value: forms.meter.label,
                onChange: function (event) {
                  props.setFormField("meter", "label", event.target.value);
                },
                required: true,
              })
            ),
            e(
              "label",
              null,
              "Zählerart optional",
              e("input", {
                value: forms.meter.meter_type,
                onChange: function (event) {
                  props.setFormField("meter", "meter_type", event.target.value);
                },
              })
            ),
            e(
              "label",
              null,
              "Messeinheit",
              e("input", {
                value: forms.meter.unit,
                onChange: function (event) {
                  props.setFormField("meter", "unit", event.target.value);
                },
                required: true,
              })
            ),
            e(
              "label",
              null,
              "Seriennummer optional",
              e("input", {
                value: forms.meter.serial_number,
                onChange: function (event) {
                  props.setFormField("meter", "serial_number", event.target.value);
                },
              })
            ),
            e(
              "button",
              { type: "submit", disabled: props.saving || props.loading },
              props.saving ? "Speichert ..." : isEditing ? "Zähler aktualisieren" : "Zähler speichern"
            ),
            isEditing
              ? e(
                  "button",
                  {
                    type: "button",
                    className: "action-button secondary",
                    disabled: props.saving || props.loading,
                    onClick: function () {
                      handleCancelEdit("meters");
                    },
                  },
                  "Bearbeitung abbrechen"
                )
              : null
          )
        ),
        isEditing
          ? null
          : e(
              "form",
              { onSubmit: props.handleMeterReadingSubmit },
          e("h4", null, "Zählerstand erfassen"),
          e(
            "div",
            { className: "form-grid" },
            e(
              "label",
              null,
              "Zähler",
              e(
                "select",
                {
                  value: forms.meterReading.meter_id,
                  onChange: function (event) {
                    props.setActiveMeterSelection(event.target.value);
                  },
                  required: true,
                },
                e("option", { value: "" }, "Zähler wählen"),
                props.meterOptions
              )
            ),
            e(
              "label",
              null,
              "Zählerstand Datum",
              e("input", {
                type: "date",
                value: forms.meterReading.reading_date,
                onChange: function (event) {
                  props.setFormField("meterReading", "reading_date", event.target.value);
                },
                required: true,
              })
            ),
            e(
              "label",
              null,
              "Zählerstand",
              e("input", {
                type: "number",
                step: "0.01",
                value: forms.meterReading.reading_value,
                onChange: function (event) {
                  props.setFormField("meterReading", "reading_value", event.target.value);
                },
                required: true,
              })
            ),
            e(
              "button",
              { type: "submit", disabled: props.saving || props.loading },
              props.saving ? "Speichert ..." : "Zählerstand speichern"
            )
          )
          )
      );
    } else {
      activeHeading = "Kosten erfassen";
      activeForm = renderExpenseForm({
        formState: forms.expense,
        onSubmit: props.handleExpenseSubmit,
        setField: function (field, value) {
          props.setFormField("expense", field, value);
        },
        setExpenseCategory: props.setExpenseCategoryValue,
        setTargetValue: props.setExpenseTargetValue,
        setMeterId: props.setExpenseMeterId,
        submitLabel: "Kosten speichern",
        extraAction: null,
        overview: props.overview,
        expenseTargetOptions: props.expenseTargetOptions,
        expenseCategorySuggestions: props.expenseCategorySuggestions,
        meterOptions: props.expenseMeterOptions,
        calculateMeterConsumptionValue: props.calculateMeterConsumptionValue,
        saving: props.saving,
        loading: props.loading,
      });
    }

    return {
      activeHeading: activeHeading,
      activeForm: activeForm,
    };
  }

  window.EasyPrentAppForms = {
    renderExpenseForm: renderExpenseForm,
    renderManagementActiveForm: renderManagementActiveForm,
  };
})();
