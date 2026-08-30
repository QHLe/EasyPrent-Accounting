(function () {
  if (!window.React) {
    return;
  }

  const e = React.createElement;
  const bootstrap = window.__EASYPRENT_BOOTSTRAP__ || {
    settlementPeriodStart: "2025-01-01",
    settlementPeriodEnd: "2025-12-31",
    depreciationYear: 2025,
    openApiUrl: "/openapi.json",
  };

  function fetchJson(url, options) {
    return fetch(url, options).then(async function (response) {
      const text = await response.text();
      const payload = text ? JSON.parse(text) : {};
      if (!response.ok) {
        throw new Error(payload.error || response.statusText);
      }
      return payload;
    });
  }

  function table(headers, rows) {
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
  }

  function summaryCards(summary) {
    return Object.keys(summary || {}).map(function (key) {
      return e(
        "article",
        { className: "card", key: key },
        e("h3", null, key.replace(/_/g, " ")),
        e("p", null, String(summary[key]))
      );
    });
  }

  function toIntegerOrNull(value) {
    return value === "" || value === null || typeof value === "undefined" ? null : Number(value);
  }

  function formatAddress(entity) {
    if (!entity) {
      return "Keine Adresse";
    }

    const street = entity.street || "";
    const cityLine = [entity.postal_code || "", entity.city || ""].join(" ").trim();
    return [street, cityLine].filter(Boolean).join(", ") || "Keine Adresse";
  }

  function formatDisplayName(entity) {
    const baseName = entity.name || entity.label || ("ID " + String(entity.id));
    return entity.is_archived ? baseName + " (archiviert)" : baseName;
  }

  function findFirstActiveObjectId(overviewPayload, objectType) {
    const collectionName =
      objectType === "building"
        ? "buildings"
        : objectType === "unit"
          ? "units"
          : objectType === "room"
            ? "rooms"
            : "properties";
    const firstItem = ((overviewPayload && overviewPayload[collectionName]) || []).find(function (item) {
      return !item.is_archived;
    });
    return firstItem ? String(firstItem.id) : "";
  }

  function findFirstActiveMeterId(overviewPayload) {
    const firstItem = ((overviewPayload && overviewPayload.meters) || []).find(function (item) {
      return !item.is_archived;
    });
    return firstItem ? String(firstItem.id) : "";
  }

  function formatObjectTypeLabel(objectType) {
    if (objectType === "building") {
      return "Gebäude";
    }
    if (objectType === "unit") {
      return "Wohnung";
    }
    if (objectType === "room") {
      return "Zimmer";
    }
    return "Anlage";
  }

  function formatExpenseWindow(expense) {
    if (expense.charge_type === "one_time") {
      if (expense.period_start && expense.period_end) {
        return [expense.period_start, expense.period_end].join(" bis ");
      }
      return expense.booking_date || expense.period_start || "Kein Datum";
    }
    if (expense.is_open_ended) {
      return [expense.period_start, "laufend"].filter(Boolean).join(" bis ");
    }
    return [expense.period_start, expense.period_end].filter(Boolean).join(" bis ") || "Kein Zeitraum";
  }

  function resolveExpenseSortEndDate(expense) {
    return String(expense.period_end || expense.booking_date || expense.period_start || "");
  }

  function sortExpensesByEndDateDesc(left, right) {
    const leftEndDate = resolveExpenseSortEndDate(left);
    const rightEndDate = resolveExpenseSortEndDate(right);
    if (leftEndDate === rightEndDate) {
      return Number(right.id || 0) - Number(left.id || 0);
    }
    if (leftEndDate === "") {
      return 1;
    }
    if (rightEndDate === "") {
      return -1;
    }
    return leftEndDate < rightEndDate ? 1 : -1;
  }

  function createExpenseFormState() {
    return {
      object_type: "property",
      object_id: "",
      expense_category: "",
      label: "",
      beneficiary_name: "",
      amount: "",
      allocation_method: "area",
      charge_type: "one_time",
      interval: "monthly",
      booking_date: bootstrap.settlementPeriodStart,
      one_time_period_enabled: false,
      period_start: bootstrap.settlementPeriodStart,
      period_end: bootstrap.settlementPeriodEnd,
      meter_id: "",
      consumption_unit: "",
      consumption_value: "",
      conversion_factor: "",
    };
  }

  function expenseFormFromExpense(expense) {
    const formState = createExpenseFormState();
    const chargeType =
      expense.charge_type === "consumption"
        ? "consumption"
        : expense.charge_type === "one_time"
          ? "one_time"
          : "recurring";
    return Object.assign({}, formState, {
      object_type: expense.object_type || formState.object_type,
      object_id:
        expense.object_id === null || typeof expense.object_id === "undefined"
          ? ""
          : String(expense.object_id),
      expense_category: expense.expense_category || expense.label || "",
      label: expense.label || expense.expense_category || "",
      beneficiary_name: expense.beneficiary_name || "",
      amount: expense.amount == null ? "" : String(expense.amount),
      allocation_method: expense.allocation_method || formState.allocation_method,
      charge_type: chargeType,
      interval:
        expense.interval_name ||
        (expense.charge_type === "yearly" ? "yearly" : formState.interval),
      booking_date: expense.booking_date || formState.booking_date,
      one_time_period_enabled:
        expense.charge_type === "one_time" &&
        !!expense.period_start &&
        !!expense.period_end &&
        (
          !expense.booking_date ||
          expense.period_start !== expense.booking_date ||
          expense.period_end !== expense.booking_date
        ),
      period_start: expense.period_start || formState.period_start,
      period_end: expense.is_open_ended ? "" : expense.period_end || formState.period_end,
      meter_id:
        expense.meter_id === null || typeof expense.meter_id === "undefined"
          ? ""
          : String(expense.meter_id),
      consumption_unit: expense.consumption_unit || "",
      consumption_value:
        expense.consumption_value == null ? "" : String(expense.consumption_value),
      conversion_factor:
        expense.conversion_factor == null || String(expense.conversion_factor) === "1"
          ? ""
          : String(expense.conversion_factor),
    });
  }

  function buildExpensePayload(formState) {
    const payload = {
      object_type: formState.object_type,
      object_id: Number(formState.object_id),
      expense_category: formState.expense_category,
      label: formState.label,
      beneficiary_name: formState.beneficiary_name,
      amount: formState.amount,
      allocation_method: formState.allocation_method,
    };

    if (formState.charge_type === "one_time") {
      payload.recurrence = "one_time";
      payload.period_start = formState.period_start;
      payload.period_end = formState.period_end;
      return payload;
    }

    payload.period_start = formState.period_start;
    payload.period_end = formState.period_end;

    if (formState.charge_type === "recurring") {
      payload.recurrence = "recurring";
      payload.interval = formState.interval;
      return payload;
    }

    payload.charge_type = "consumption";
    if (formState.meter_id) {
      payload.meter_id = Number(formState.meter_id);
    }
    if (formState.consumption_unit !== "") {
      payload.consumption_unit = formState.consumption_unit;
    }
    if (formState.meter_id === "" && formState.consumption_value !== "") {
      payload.consumption_value = formState.consumption_value;
    }
    if (formState.conversion_factor !== "") {
      payload.conversion_factor = formState.conversion_factor;
    }
    return payload;
  }

  function buildObjectTargetValue(objectType, objectId) {
    if (!objectType || objectId === "" || objectId === null || typeof objectId === "undefined") {
      return "";
    }
    return String(objectType) + ":" + String(objectId);
  }

  function parseObjectTargetValue(value) {
    const parts = String(value || "").split(":");
    if (parts.length !== 2 || !parts[0] || !parts[1]) {
      return null;
    }
    return {
      object_type: parts[0],
      object_id: parts[1],
    };
  }

  function formatExpenseTargetLabel(expense) {
    const objectName = expense.object_name || ("ID " + String(expense.object_id));
    return formatObjectTypeLabel(expense.object_type) + ": " + objectName;
  }

  function formatExpenseCategoryLabel(expense) {
    const baseName = expense.expense_category || expense.label || ("ID " + String(expense.id));
    return expense.is_archived ? baseName + " (archiviert)" : baseName;
  }

  function formatExpenseBillingType(expense) {
    if (expense.charge_type === "consumption") {
      return "Verbrauchsbezogen";
    }
    if (expense.charge_type === "one_time") {
      return "Gesamtkosten";
    }
    return "Wiederholend";
  }

  function formatExpenseCadence(expense) {
    if (expense.charge_type === "consumption") {
      return "verbrauchsbasiert";
    }
    if (expense.charge_type === "yearly") {
      return "jährlich";
    }
    if (expense.charge_type === "monthly") {
      return "monatlich";
    }
    return "gesamt";
  }

  function formatMoneyValue(value) {
    if (value === null || value === "" || typeof value === "undefined") {
      return "-";
    }
    const numericValue = Number(value);
    if (Number.isNaN(numericValue)) {
      return String(value);
    }
    return numericValue.toFixed(2);
  }

  function formatExpenseAmountValue(expense) {
    return expense.amount == null || expense.amount === ""
      ? "-"
      : String(expense.amount);
  }

  function formatNumericLabel(value) {
    if (value == null || Number.isNaN(value)) {
      return "-";
    }
    const rounded = Math.round(value * 100) / 100;
    return Number.isInteger(rounded) ? String(rounded) : String(rounded.toFixed(2));
  }

  window.EasyPrentAppDomain = {
    buildExpensePayload: buildExpensePayload,
    buildObjectTargetValue: buildObjectTargetValue,
    createExpenseFormState: createExpenseFormState,
    expenseFormFromExpense: expenseFormFromExpense,
    fetchJson: fetchJson,
    findFirstActiveMeterId: findFirstActiveMeterId,
    findFirstActiveObjectId: findFirstActiveObjectId,
    formatAddress: formatAddress,
    formatDisplayName: formatDisplayName,
    formatExpenseAmountValue: formatExpenseAmountValue,
    formatExpenseBillingType: formatExpenseBillingType,
    formatExpenseCadence: formatExpenseCadence,
    formatExpenseCategoryLabel: formatExpenseCategoryLabel,
    formatExpenseTargetLabel: formatExpenseTargetLabel,
    formatExpenseWindow: formatExpenseWindow,
    formatMoneyValue: formatMoneyValue,
    formatNumericLabel: formatNumericLabel,
    formatObjectTypeLabel: formatObjectTypeLabel,
    parseObjectTargetValue: parseObjectTargetValue,
    resolveExpenseSortEndDate: resolveExpenseSortEndDate,
    sortExpensesByEndDateDesc: sortExpensesByEndDateDesc,
    summaryCards: summaryCards,
    table: table,
    toIntegerOrNull: toIntegerOrNull,
  };
})();
