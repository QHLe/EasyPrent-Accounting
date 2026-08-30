(function () {
  if (!window.React) {
    return;
  }

  const e = React.createElement;
  const Fragment = React.Fragment;
  const domain = window.EasyPrentAppDomain || {};
  const charts = window.EasyPrentAppCharts || {};
  const summaryCards = domain.summaryCards;
  const table = domain.table;
  const formatMoneyValue = domain.formatMoneyValue;
  const formatDisplayName = domain.formatDisplayName;
  const formatNumericLabel = domain.formatNumericLabel;
  const MeterChart = charts.MeterChart;
  const ExpenseDevelopmentChart = charts.ExpenseDevelopmentChart;

  function AppShell(props) {
    return e(
      "div",
      { className: "app" },
      e(
        "header",
        { className: "hero" },
        e("h1", null, "Easy Property Manager"),
        e(
          "p",
          { className: "lede" },
          "Verwaltung von Anlagen, Gebäuden, Wohnungen, Zimmern, Zählern, Mietern und Kosten in einer React-Oberfläche. ",
          "Alle Formulare speichern direkt über die dokumentierten API-Endpunkte."
        ),
      ),
      e(
        "main",
        { className: "main-grid" },
        e("div", { className: "tabs" }, props.mainTabButtons),
        props.error ? e("p", { className: "status error" }, props.error) : null,
        props.status ? e("p", { className: "status success" }, props.status) : null,
        props.mainContent
      )
    );
  }

  function OverviewContent(props) {
    return e(
      "div",
      null,
      e("div", { className: "cards" }, summaryCards(props.summary)),
      e(
        "div",
        { className: "content-grid" },
        e(
          "section",
          { className: "panel" },
          e("h2", null, "Mandanten- und Rollenmodell"),
          e("ul", null, props.roleItems)
        ),
        e(
          "section",
          { className: "panel" },
          e("h2", null, "Anlagen"),
          table(["ID", "Name", "Organisation", "Ort"], props.propertyRows)
        ),
        e(
          "section",
          { className: "panel" },
          e("h2", null, "Gebäude"),
          table(["ID", "Name", "Anlage", "Adresse"], props.buildingRows)
        ),
        e(
          "section",
          { className: "panel" },
          e("h2", null, "Wohnungen"),
          table(["ID", "Bezeichnung", "Gebäude", "Adresse"], props.unitRows)
        ),
        e(
          "section",
          { className: "panel" },
          e("h2", null, "Zimmer"),
          table(["ID", "Name", "Wohnung", "Wohnfläche"], props.roomRows)
        ),
        e(
          "section",
          { className: "panel" },
          e("h2", null, "Zähler"),
          table(["ID", "Name", "Objektart", "Zielobjekt", "Einheit", "Letzter Stand"], props.meterRows)
        ),
        e(
          "section",
          { className: "panel" },
          e("h2", null, "Mietverträge"),
          table(["Mieter", "Mietobjekt", "Start", "Kaltmiete", "Vorauszahlung"], props.leaseRows)
        ),
        e(
          "section",
          { className: "panel" },
          e("h2", null, "Nebenkostenabrechnung " + String(props.depreciationYear)),
          table(["Mieter", "Mietobjekt", "Kostenanteil", "Vorauszahlungen", "Saldo"], props.settlementRows),
          props.settlement
            ? e(
                "p",
                { className: "hint" },
                "Gesamt: Kosten ",
                props.settlement.totals.costs,
                " | Vorauszahlungen ",
                props.settlement.totals.advances,
                " | Saldo ",
                props.settlement.totals.balance
              )
            : null
        ),
        e(
          "section",
          { className: "panel" },
          e("h2", null, "Kostenübersicht"),
          table(
            ["Kostenart", "Empfänger", "Abrechnungsart", "Wert (EUR)", "Gesamtsumme (EUR)", "Von", "Bis"],
            props.expenseRows
          )
        ),
        e(
          "section",
          { className: "panel" },
          e("h2", null, "Abschreibung " + String(props.depreciationYear)),
          table(["Objekt", "Methode", "AfA-Basis", "Monate", "Jahreswert"], props.depreciationRows),
          props.depreciation ? e("p", { className: "hint" }, "Gesamt-AfA: ", props.depreciation.total) : null
        )
      )
    );
  }

  function SettingsContent(props) {
    return e(
      "div",
      { className: "content-grid" },
      e(
        "section",
        { className: "panel panel-wide" },
        e("h2", null, "Einstellungen"),
        e(
          "p",
          { className: "hint" },
          "Paperless-Zugang für den Upload und die Referenzierung von Rechnungen konfigurieren."
        ),
        e(
          "form",
          { onSubmit: props.onPaperlessSubmit },
          e(
            "div",
            { className: "form-grid" },
            e(
              "label",
              null,
              "Paperless URL",
              e("input", {
                type: "url",
                value: props.paperlessForm.base_url,
                onChange: function (event) {
                  props.onFieldChange("base_url", event.target.value);
                },
                placeholder: "https://paperless.example.org",
                required: true,
              })
            ),
            e(
              "label",
              null,
              "Paperless Token",
              e("input", {
                type: "password",
                value: props.paperlessForm.api_token,
                onChange: function (event) {
                  props.onFieldChange("api_token", event.target.value);
                },
                placeholder: props.paperlessSettings.token_present
                  ? "Leer lassen, um bestehenden Token zu behalten"
                  : "",
                required: !props.paperlessSettings.token_present,
              })
            ),
            e(
              "p",
              { className: "hint" },
              "Token (maskiert): ",
              props.paperlessSettings.token_masked || "Nicht gesetzt"
            ),
            e(
              "p",
              { className: "hint" },
              "Serverstatus: ",
              props.serverStatus.reachable ? "erreichbar" : "nicht erreichbar"
            ),
            e(
              "p",
              { className: "hint" },
              "Paperless Serverstatus: ",
              props.paperlessStatus.message ||
                (props.paperlessStatus.reachable ? "erreichbar" : "nicht erreichbar")
            ),
            props.paperlessSettings.updated_at
              ? e(
                  "p",
                  { className: "hint" },
                  "Letzte Aktualisierung: " + props.paperlessSettings.updated_at
                )
              : null,
            e(
              "button",
              { type: "submit", disabled: props.isActionDisabled },
              props.saving ? "Speichert ..." : "Einstellungen speichern"
            )
          )
        ),
        e(
          "form",
          { onSubmit: props.onApplicationSettingsSubmit },
          e("h3", null, "Darstellung"),
          e(
            "div",
            { className: "form-grid" },
            e(
              "label",
              null,
              e("span", null, "Löschaktionen anzeigen"),
              e("input", {
                type: "checkbox",
                checked: !!props.applicationSettingsForm.show_delete_actions,
                onChange: function (event) {
                  props.onApplicationSettingsFieldChange(
                    "show_delete_actions",
                    !!event.target.checked
                  );
                },
              })
            ),
            e(
              "p",
              { className: "hint" },
              props.applicationSettings.updated_at
                ? "Letzte Aktualisierung: " + props.applicationSettings.updated_at
                : "Standard: Löschaktionen sind sichtbar."
            ),
            e(
              "button",
              { type: "submit", disabled: props.isActionDisabled },
              props.saving ? "Speichert ..." : "Darstellung speichern"
            )
          )
        ),
        e(
          "form",
          { onSubmit: props.onApplicationImportSubmit },
          e("h3", null, "Import / Export"),
          e(
            "p",
            { className: "hint" },
            "Daten exportieren erstellt eine portable Sicherungsdatei. Import überschreibt den aktuellen Datenbestand vollständig mit einer zuvor exportierten Datei."
          ),
          e(
            "div",
            { className: "form-grid" },
            e(
              "div",
              { className: "inline-actions" },
              e(
                "button",
                {
                  type: "button",
                  disabled: props.isActionDisabled,
                  onClick: props.onApplicationExport,
                },
                "Daten exportieren"
              )
            ),
            e(
              "label",
              null,
              "Importdatei",
              e("input", {
                key: props.applicationImportInputKey,
                type: "file",
                accept: "application/json,.json",
                onChange: function (event) {
                  props.onApplicationImportFileChange(event.target.files);
                },
              })
            ),
            e(
              "p",
              { className: "hint" },
              props.applicationImportFileName
                ? "Ausgewählte Datei: " + props.applicationImportFileName
                : "Keine Importdatei ausgewählt."
            ),
            e(
              "button",
              { type: "submit", disabled: props.isActionDisabled },
              props.saving ? "Verarbeitet ..." : "Daten importieren"
            )
          )
        )
      )
    );
  }

  function MeterSupplementalPanels(props) {
    const consumptionRows = (props.meterConsumptionSummary || []).map(function (period) {
      return e(
        "tr",
        { key: "meter-consumption-" + period.timestamp },
        e("td", null, period.label),
        e("td", null, formatNumericLabel(period.value))
      );
    });
    const totalConsumption = (props.meterConsumptionSummary || []).reduce(function (total, period) {
      return total + (period.value || 0);
    }, 0);
    if (consumptionRows.length) {
      consumptionRows.push(
        e(
          "tr",
          { key: "meter-consumption-total" },
          e("th", { scope: "row" }, "Gesamt"),
          e("th", null, formatNumericLabel(totalConsumption))
        )
      );
    }

    return e(
      Fragment,
      null,
      e(
        "section",
        { className: "panel panel-wide" },
        e("h2", null, "Zählerstandhistorie"),
        e(
          "p",
          { className: "hint" },
          props.selectedMeter
            ? "Vollständige Historie für " +
                formatDisplayName(props.selectedMeter) +
                " mit gleichbleibenden oder steigenden Zählerständen."
            : "Kein Zähler ausgewählt: Es werden alle vorhandenen Zählerstände angezeigt."
        ),
        props.selectedMeter
          ? e(
              "p",
              { className: "hint" },
              "Zähler anklicken oder im Formular auswählen, um die Historie zu wechseln."
            )
          : null,
        e(
          "p",
          { className: "hint" },
          "Aktualisierung: Die Historie wird nach jeder Speicherung oder Löschung von Zählerständen neu geladen."
        ),
        table(["Zähler", "Datum", "Stand", "Einheit", "Zielobjekt", "Aktion"], props.meterReadingRows)
      ),
      e(
        "section",
        { className: "panel panel-wide" },
        e("h2", null, "Zählerentwicklung"),
        props.selectedMeter
          ? e(
              "div",
              { className: "stack" },
              e(
                "div",
                { className: "chart-controls" },
                e(
                  "label",
                  null,
                  "Zeitraum von",
                  e("input", {
                    type: "date",
                    value: props.meterChartRange.from,
                    onChange: function (event) {
                      props.onMeterChartRangeBoundaryChange("from", event.target.value);
                    },
                  })
                ),
                e(
                  "label",
                  null,
                  "Zeitraum bis",
                  e("input", {
                    type: "date",
                    value: props.meterChartRange.to,
                    onChange: function (event) {
                      props.onMeterChartRangeBoundaryChange("to", event.target.value);
                    },
                  })
                ),
                e(
                  "label",
                  null,
                  "Ansicht",
                  e(
                    "select",
                    {
                      value: props.meterChartGranularity,
                      onChange: function (event) {
                        props.onMeterChartGranularityChange(event.target.value);
                      },
                    },
                    e("option", { value: "months" }, "Letzte Monate"),
                    e("option", { value: "years" }, "Letzte Jahre")
                  )
                ),
                e(
                  "label",
                  null,
                  "Diagrammtyp",
                  e(
                    "select",
                    {
                      value: props.meterChartMode,
                      onChange: function (event) {
                        props.onMeterChartModeChange(event.target.value);
                      },
                    },
                    e("option", { value: "cumulative" }, "Kumuliert"),
                    e("option", { value: "bars" }, "Säulen")
                  )
                ),
                e(
                  "label",
                  null,
                  "Interpolation",
                  e(
                    "select",
                    {
                      value: props.meterInterpolationMode,
                      onChange: function (event) {
                        props.onMeterInterpolationModeChange(event.target.value);
                      },
                    },
                    e("option", { value: "linear" }, "Linear"),
                    e("option", { value: "quadratic" }, "Quadratisch")
                  )
                )
              ),
              e(
                "p",
                { className: "hint" },
                (props.meterChartMode === "bars"
                  ? "Säulen zeigen den Verbrauch je Zeitraum."
                  : "Kumuliert zeigt den fortlaufenden Zählerstand.") +
                  " Zeitraum: " +
                  props.meterChartRange.from +
                  " bis " +
                  props.meterChartRange.to +
                  " Zwischenstände werden " +
                  (props.meterInterpolationMode === "quadratic" ? "quadratisch" : "linear") +
                  " interpoliert. Tatsächliche Zählerstände sind zusätzlich markiert."
              ),
              e(MeterChart, {
                series: props.meterChartSeries,
                actualReadings: props.actualMeterReadings,
                chartMode: props.meterChartMode,
              }),
              e("h3", null, "Verbrauch im Zeitraum"),
              table(
                ["Zeitraum", "Verbrauch" + (props.selectedMeter.unit ? " (" + props.selectedMeter.unit + ")" : "")],
                consumptionRows
              )
            )
          : e("p", { className: "hint" }, "Zähler anklicken, um ein Diagramm zu sehen.")
      )
    );
  }

  function ExpenseDevelopmentPanel(props) {
    const monthlySeries = props.expenseDevelopmentMonthlySeries || [];
    const monthCount = monthlySeries.length;
    const categoryTotalRows = (props.expenseCategoryPeriodTotals || []).map(function (categoryTotal) {
      const isCalculable = !categoryTotal.hasUncalculatedExpense;
      return e(
        "tr",
        { key: "expense-category-period-total-" + categoryTotal.category },
        e("td", null, categoryTotal.category),
        e(
          "td",
          null,
          !isCalculable
            ? "–"
            : formatMoneyValue(categoryTotal.total) + " EUR"
        ),
        e(
          "td",
          null,
          !isCalculable || monthCount === 0
            ? "–"
            : formatMoneyValue(categoryTotal.total / monthCount) + " EUR"
        )
      );
    });

    return e(
      "section",
      { className: "panel panel-wide" },
      e("h2", null, "Kostenentwicklung"),
      e(
        "div",
        { className: "stack" },
        e(
          "div",
          { className: "chart-controls" },
          e(
            "label",
            null,
            "Kosten-Granularität",
            e(
              "select",
              {
                value: props.expenseChartConfig.granularity,
                onChange: function (event) {
                  props.onExpenseChartConfigChange({ granularity: event.target.value });
                },
              },
              e("option", { value: "months" }, "Monatlich"),
              e("option", { value: "years" }, "Jährlich")
            )
          ),
          e(
            "label",
            null,
            "Kosten-Diagrammtyp",
            e(
              "select",
              {
                value: props.expenseChartConfig.mode,
                onChange: function (event) {
                  props.onExpenseChartConfigChange({ mode: event.target.value });
                },
              },
              e("option", { value: "bars" }, "Säulen"),
              e("option", { value: "line" }, "Linie")
            )
          ),
          e(
            "label",
            null,
            "Archivstatus",
            e(
              "select",
              {
                value: props.expenseChartConfig.include_archived ? "all" : "active",
                onChange: function (event) {
                  props.onExpenseChartConfigChange({
                    include_archived: event.target.value === "all",
                  });
                },
              },
              e("option", { value: "active" }, "Nur aktive Kosten"),
              e("option", { value: "all" }, "Aktive und archivierte Kosten")
            )
          )
        ),
        e(
          "p",
          { className: "hint" },
          "Der Graph nutzt die aktuelle Kostenlisten-Filterung (Zielobjekt und Kostenart), skaliert die Y-Achse automatisch auf die tatsächlichen EUR-Werte und zeigt im Säulendiagramm farbige Kostenanteile je Kostenart."
        ),
        e(ExpenseDevelopmentChart, {
          series: props.expenseDevelopmentSeries,
          compositionSeries: props.expenseDevelopmentCompositionSeries,
          chartMode: props.expenseChartConfig.mode,
        }),
        e(
          "div",
          { className: "expense-development-table" },
          e("h3", null, "Gesamtkosten je Kostenart"),
          e(
            "div",
            { className: "chart-controls" },
            e(
              "label",
              null,
              "Zeitraum von",
              e("input", {
                type: "date",
                value: props.expenseCategoryPeriod.from,
                onChange: function (event) {
                  props.onExpenseCategoryPeriodChange("from", event.target.value);
                },
              })
            ),
            e(
              "label",
              null,
              "Zeitraum bis",
              e("input", {
                type: "date",
                value: props.expenseCategoryPeriod.to,
                onChange: function (event) {
                  props.onExpenseCategoryPeriodChange("to", event.target.value);
                },
              })
            )
          ),
          e(
            "p",
            { className: "hint" },
            "Aktive Kosten gemäß den gesetzten Filtern, anteilig für den gewählten Zeitraum. Ein Strich bedeutet, dass mindestens eine Kostenposition noch nicht berechnet werden kann."
          ),
          table(
            ["Kostenart", "Gesamtkosten (EUR)", "Durchschnitt pro Monat (EUR)"],
            categoryTotalRows
          )
        )
      )
    );
  }

  function ManagementContent(props) {
    return e(
      "div",
      { className: "content-grid" },
      e(
        "section",
        { className: "panel panel-wide" },
        e("h2", null, props.createActionLabel),
        e("div", { className: "tabs" }, props.managementTabButtons),
        e("p", { className: "hint" }, props.managementHint),
        e(
          "div",
          { className: "inline-actions" },
          e(
            "button",
            {
              type: "button",
              className: "action-button secondary",
              disabled: props.isActionDisabled,
              onClick: props.onToggleCreateForm,
            },
            props.shouldShowActiveForm ? "Erfassung ausblenden" : props.createActionLabel
          )
        ),
        props.shouldShowActiveForm
          ? e(Fragment, null, e("h3", null, props.activeHeading), props.activeForm)
          : e(
              "p",
              { className: "hint" },
              "Erfassungsfelder sind ausgeblendet. Klicke auf ",
              props.createActionLabel,
              "."
            )
      ),
      e(
        "section",
        { className: "panel panel-wide" },
        e(
          "div",
          { className: "panel-heading" },
          e("h2", null, props.previewTitle),
          props.isPreviewCollapsible
            ? e(
                "button",
                {
                  type: "button",
                  className: "panel-toggle",
                  onClick: props.onTogglePreview,
                  "aria-label": props.isPreviewExpanded
                    ? "Kostenliste einklappen"
                    : "Kostenliste ausklappen",
                  title: props.isPreviewExpanded
                    ? "Kostenliste einklappen"
                    : "Kostenliste ausklappen",
                },
                props.isPreviewExpanded ? "▾" : "▸"
              )
            : null
        ),
        props.isPreviewExpanded
          ? e(
              Fragment,
              null,
              e("p", { className: "hint" }, props.previewDescription),
              props.previewToolbar,
              table(props.previewHeaders, props.previewRows)
            )
          : e(
              "p",
              { className: "hint" },
              "Die Kostenliste ist eingeklappt. Über den Button oben blendest du Filter und Einträge wieder ein."
            )
      ),
      props.supplementalContent
    );
  }

  window.EasyPrentAppSections = {
    AppShell: AppShell,
    ExpenseDevelopmentPanel: ExpenseDevelopmentPanel,
    ManagementContent: ManagementContent,
    MeterSupplementalPanels: MeterSupplementalPanels,
    OverviewContent: OverviewContent,
    SettingsContent: SettingsContent,
  };
})();
