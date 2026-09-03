(function () {
  if (!window.React) {
    return;
  }

  const e = React.createElement;
  const Fragment = React.Fragment;
  const useState = React.useState;
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
    const settlementProperties = (props.properties || []).filter(function (property) {
      return !property.is_archived;
    });
    const standaloneSettlementUnits = (props.units || []).filter(function (unit) {
      return !unit.is_archived && !unit.property_id;
    });
    const settlementTargetValue = props.settlementFilters.unit_id
      ? "unit:" + String(props.settlementFilters.unit_id)
      : props.settlementFilters.property_id
        ? "property:" + String(props.settlementFilters.property_id)
        : "";
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
          table(["Mieter", "Mietobjekt", "Start", "Kaltmiete", "NK-Vorauszahlung/Monat"], props.leaseRows)
        ),
        e(
          "section",
          { className: "panel" },
          e("h2", null, "Nebenkostenabrechnung"),
          e(
            "form",
            { className: "inline-form", onSubmit: props.onSettlementFilterSubmit },
            e(
              "label",
              null,
              "Objekt",
              e(
                "select",
                {
                  name: "settlement_target",
                  value: settlementTargetValue,
                  onChange: props.onSettlementFilterChange,
                },
                e("option", { value: "" }, "Objekt auswählen"),
                settlementProperties.map(function (property) {
                  return e(
                    "option",
                    { key: "property-" + property.id, value: "property:" + property.id },
                    "Immobilie: " + property.name
                  );
                }),
                standaloneSettlementUnits.map(function (unit) {
                  return e(
                    "option",
                    { key: "unit-" + unit.id, value: "unit:" + unit.id },
                    "Wohnung: " + unit.label
                  );
                })
              )
            ),
            e("label", null, "Von", e("input", { type: "date", name: "period_start", value: props.settlementFilters.period_start, onChange: props.onSettlementFilterChange })),
            e("label", null, "Bis", e("input", { type: "date", name: "period_end", value: props.settlementFilters.period_end, onChange: props.onSettlementFilterChange })),
            e("button", { type: "submit", disabled: !settlementTargetValue }, "Abrechnung aktualisieren")
          ),
          table(
            [
              "Mieter",
              "Mietobjekt",
              "Abgerechneter Zeitraum",
              "Kostenanteil",
              "Geleistete Vorauszahlungen",
              "Saldo",
              "Dokument",
            ],
            props.settlementRows
          ),
          e(
            "p",
            { className: "hint" },
            "Beim Aktualisieren werden fehlende GnuCash-Nebenkostenvorauszahlungen " +
              "für den gewählten Zeitraum eingelesen. Der Buchungsmonat zählt."
          ),
          props.settlement
            ? e(
                "p",
                { className: "hint" },
                "Gesamt: Kosten ",
                props.settlement.totals.costs,
                " · Vorauszahlungen ",
                props.settlement.totals.advances == null ? "-" : props.settlement.totals.advances,
                " · Saldo ",
                props.settlement.totals.balance == null ? "-" : props.settlement.totals.balance
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
          { onSubmit: props.onGnuCashSubmit },
          e("h3", null, "GnuCash-Zahlungsimport"),
          e(
            "p",
            { className: "hint" },
            "Der Abrechnungs-Button liest Nebenkostenvorauszahlungen ausschließlich lesend aus dem PostgreSQL-GnuCash-Buch."
          ),
          e(
            "div",
            { className: "form-grid" },
            e(
              "label",
              null,
              "Host",
              e("input", {
                value: props.gnucashForm.host,
                onChange: function (event) { props.onGnuCashFieldChange("host", event.target.value); },
                required: true,
              })
            ),
            e(
              "label",
              null,
              "Port",
              e("input", {
                type: "number",
                min: "1",
                max: "65535",
                value: props.gnucashForm.port,
                onChange: function (event) { props.onGnuCashFieldChange("port", event.target.value); },
                required: true,
              })
            ),
            e(
              "label",
              null,
              "Datenbank",
              e("input", {
                value: props.gnucashForm.database,
                onChange: function (event) { props.onGnuCashFieldChange("database", event.target.value); },
                required: true,
              })
            ),
            e(
              "label",
              null,
              "Benutzer",
              e("input", {
                value: props.gnucashForm.username,
                onChange: function (event) { props.onGnuCashFieldChange("username", event.target.value); },
                required: true,
              })
            ),
            e(
              "label",
              null,
              "Passwort",
              e("input", {
                type: "password",
                value: props.gnucashForm.password,
                placeholder: props.gnucashSettings.password_present
                  ? "Leer lassen, um das gespeicherte Passwort zu behalten"
                  : "",
                onChange: function (event) { props.onGnuCashFieldChange("password", event.target.value); },
                required: !props.gnucashSettings.password_present,
              })
            ),
            e(
              "label",
              null,
              "TLS-Modus",
              e(
                "select",
                {
                  value: props.gnucashForm.sslmode,
                  onChange: function (event) { props.onGnuCashFieldChange("sslmode", event.target.value); },
                },
                ["require", "verify-ca", "verify-full", "prefer", "allow", "disable"].map(function (mode) {
                  return e("option", { key: mode, value: mode }, mode);
                })
              )
            ),
            e(
              "p",
              { className: "hint" },
              "Passwort (maskiert): ",
              props.gnucashSettings.password_masked || "Nicht gesetzt"
            ),
            e(
              "button",
              { type: "submit", disabled: props.isActionDisabled },
              props.saving ? "Speichert ..." : "GnuCash-Einstellungen speichern"
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
    const [expandedCategories, setExpandedCategories] = useState({});
    const monthlySeries = props.expenseDevelopmentMonthlySeries || [];
    const monthCount = monthlySeries.length;
    const categoryPeriodTotals = props.expenseCategoryPeriodTotals || [];
    const hasUncalculatedExpense = categoryPeriodTotals.some(function (categoryTotal) {
      return categoryTotal.hasUncalculatedExpense;
    });
    const totalCategoryCosts = categoryPeriodTotals.reduce(function (total, categoryTotal) {
      return total + Number(categoryTotal.total || 0);
    }, 0);
    function formatCalculationAmount(amount, isInterpolated) {
      return amount == null
        ? "–"
        : formatMoneyValue(amount) + " EUR" + (isInterpolated ? " (2)" : "");
    }

    function formatCalculationAverage(amount, isInterpolated) {
      return amount == null || monthCount === 0
        ? "–"
        : formatCalculationAmount(amount / monthCount, isInterpolated);
    }

    function formatConsumption(value, unit) {
      return value == null ? "–" : formatNumericLabel(value) + (unit ? " " + unit : "");
    }

    const categoryTotalRows = [];
    categoryPeriodTotals.forEach(function (categoryTotal) {
      const isCalculable = !categoryTotal.hasUncalculatedExpense;
      const isExpanded = !!expandedCategories[categoryTotal.category];
      const items = categoryTotal.items || [];
      if (items.length === 1) {
        const item = items[0];
        categoryTotalRows.push(
          e(
            "tr",
            { key: "expense-category-item-" + categoryTotal.category + "-" + item.id },
            e("td", null, item.label + (item.beneficiary_name ? " (" + item.beneficiary_name + ")" : "")),
            e("td", null, formatCalculationAmount(item.amount, item.isInterpolated)),
            e("td", null, formatCalculationAverage(item.amount, item.isInterpolated)),
            e("td", null, formatConsumption(item.consumptionValue, item.consumptionUnit))
          )
        );
        return;
      }
      categoryTotalRows.push(e(
        "tr",
        {
          className: "selectable-row",
          key: "expense-category-period-total-" + categoryTotal.category,
          role: "button",
          tabIndex: 0,
          "aria-expanded": isExpanded,
          onClick: function () {
            setExpandedCategories(function (current) {
              return Object.assign({}, current, {
                [categoryTotal.category]: !current[categoryTotal.category],
              });
            });
          },
          onKeyDown: function (event) {
            if (event.key === "Enter" || event.key === " ") {
              event.preventDefault();
              event.currentTarget.click();
            }
          },
        },
        e("td", null, categoryTotal.category),
        e(
          "td",
          null,
          !isCalculable
            ? "–"
            : formatCalculationAmount(categoryTotal.total, categoryTotal.hasInterpolatedExpense)
        ),
        e(
          "td",
          null,
          !isCalculable || monthCount === 0
            ? "–"
            : formatCalculationAmount(
                categoryTotal.total / monthCount,
                categoryTotal.hasInterpolatedExpense
              )
        ),
        e("td", null, "–")
      ));
      if (isExpanded) {
        items.forEach(function (item) {
          categoryTotalRows.push(
            e(
              "tr",
              { className: "expense-detail-row", key: "expense-category-item-" + categoryTotal.category + "-" + item.id },
              e("td", null, item.label + (item.beneficiary_name ? " (" + item.beneficiary_name + ")" : "")),
              e("td", null, formatCalculationAmount(item.amount, item.isInterpolated)),
              e("td", null, formatCalculationAverage(item.amount, item.isInterpolated)),
              e("td", null, formatConsumption(item.consumptionValue, item.consumptionUnit))
            )
          );
        });
      }
    });
    categoryTotalRows.push(
      e(
        "tr",
        { className: "table-total", key: "expense-category-period-total" },
        e("th", { scope: "row" }, "Total"),
        e(
          "th",
          null,
          hasUncalculatedExpense
            ? "–"
            : formatCalculationAmount(
                totalCategoryCosts,
                categoryPeriodTotals.some(function (categoryTotal) {
                  return categoryTotal.hasInterpolatedExpense;
                })
              )
        ),
        e(
          "th",
          null,
          hasUncalculatedExpense || monthCount === 0
            ? "–"
            : formatCalculationAmount(
                totalCategoryCosts / monthCount,
                categoryPeriodTotals.some(function (categoryTotal) {
                  return categoryTotal.hasInterpolatedExpense;
                })
              )
        ),
        e("th", null, "–")
      )
    );

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
            ["Kostenart", "Gesamtkosten (EUR)", "Durchschnitt pro Monat (EUR)", "Verbrauch"],
            categoryTotalRows
          ),
          e(
            "p",
            { className: "hint" },
            "Legende: (2) interpoliert, etwa bei zeitanteilig verteilten Gesamtkosten oder zwischen zwei Zählerständen."
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
        })
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
