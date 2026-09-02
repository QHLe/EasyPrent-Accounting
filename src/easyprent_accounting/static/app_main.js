(function () {
  const rootNode = document.getElementById("root");
  if (!rootNode || !window.React || !window.ReactDOM) {
    return;
  }

  const e = React.createElement;
  const useEffect = React.useEffect;
  const useState = React.useState;
  const bootstrap = window.__EASYPRENT_BOOTSTRAP__ || {
    settlementPeriodStart: "2025-01-01",
    settlementPeriodEnd: "2025-12-31",
    depreciationYear: 2025,
    openApiUrl: "/openapi.json",
  };
  const domain = window.EasyPrentAppDomain || {};
  const sections = window.EasyPrentAppSections || {};
  const formsModule = window.EasyPrentAppForms || {};
  const previews = window.EasyPrentAppPreviews || {};
  const buildExpensePayload = domain.buildExpensePayload;
  const buildObjectTargetValue = domain.buildObjectTargetValue;
  const createExpenseFormState = domain.createExpenseFormState;
  const expenseFormFromExpense = domain.expenseFormFromExpense;
  const fetchJson = domain.fetchJson;
  const findFirstActiveObjectId = domain.findFirstActiveObjectId;
  const formatDisplayName = domain.formatDisplayName;
  const formatMoneyValue = domain.formatMoneyValue;
  const parseObjectTargetValue = domain.parseObjectTargetValue;
  const toIntegerOrNull = domain.toIntegerOrNull;
  const AppShell = sections.AppShell;
  const ExpenseDevelopmentPanel = sections.ExpenseDevelopmentPanel;
  const ManagementContent = sections.ManagementContent;
  const MeterSupplementalPanels = sections.MeterSupplementalPanels;
  const OverviewContent = sections.OverviewContent;
  const SettingsContent = sections.SettingsContent;
  const renderManagementActiveForm = formsModule.renderManagementActiveForm;
  const buildFilteredExpenses = previews.buildFilteredExpenses || function (expenses) {
    return expenses || [];
  };
  const buildManagementPreview = previews.buildManagementPreview || function () {
    return {
      previewTitle: "Objektliste",
      previewDescription: "",
      previewToolbar: null,
      previewHeaders: [],
      previewRows: [],
    };
  };
  const buildMeterData = previews.buildMeterData || function () {
    return {
      selectedMeter: null,
      selectedMeterReadings: [],
      meterReadingRows: [],
    };
  };
  const buildOverviewRows = previews.buildOverviewRows || function () {
    return {
      roleItems: [],
      propertyRows: [],
      buildingRows: [],
      unitRows: [],
      roomRows: [],
      meterRows: [],
      leaseRows: [],
      expenseRows: [],
      settlementRows: [],
      depreciationRows: [],
    };
  };

  function parseIsoDate(dateString) {
    const parts = String(dateString || "").split("-").map(Number);
    return new Date(Date.UTC(parts[0] || 1970, (parts[1] || 1) - 1, parts[2] || 1));
  }

  function formatIsoDate(date) {
    return [
      String(date.getUTCFullYear()),
      String(date.getUTCMonth() + 1).padStart(2, "0"),
      String(date.getUTCDate()).padStart(2, "0"),
    ].join("-");
  }

  function shiftIsoDateByMonths(isoDate, months) {
    const source = parseIsoDate(isoDate);
    const shifted = new Date(
      Date.UTC(source.getUTCFullYear(), source.getUTCMonth() + months, source.getUTCDate())
    );
    return formatIsoDate(shifted);
  }

  function buildDefaultMeterChartRange(readings) {
    const endDate =
      readings && readings.length
        ? readings[readings.length - 1].reading_date
        : formatIsoDate(new Date());
    return {
      from: shiftIsoDateByMonths(endDate, -12),
      to: endDate,
    };
  }

  function interpolateReading(readings, targetDateString) {
    if (!readings.length) {
      return null;
    }
    const targetTime = parseIsoDate(targetDateString).getTime();
    let previous = null;
    for (let index = 0; index < readings.length; index += 1) {
      const reading = readings[index];
      const currentTime = parseIsoDate(reading.reading_date).getTime();
      const currentValue = Number(reading.reading_value);
      if (currentTime === targetTime) {
        return { value: currentValue, isInterpolated: false };
      }
      if (currentTime > targetTime) {
        if (!previous) {
          return { value: currentValue, isInterpolated: false };
        }
        const previousTime = parseIsoDate(previous.reading_date).getTime();
        const previousValue = Number(previous.reading_value);
        const totalDistance = currentTime - previousTime;
        if (totalDistance <= 0) {
          return { value: previousValue, isInterpolated: true };
        }
        const factor = (targetTime - previousTime) / totalDistance;
        return {
          value: previousValue + (currentValue - previousValue) * factor,
          isInterpolated: true,
        };
      }
      previous = reading;
    }
    return previous ? { value: Number(previous.reading_value), isInterpolated: false } : null;
  }

  function interpolateReadingValue(readings, targetDateString) {
    const reading = interpolateReading(readings, targetDateString);
    return reading ? reading.value : null;
  }

  function calculateMeterConsumptionValue(meterId, periodStart, periodEnd, overviewPayload) {
    const calculation = calculateMeterConsumption(meterId, periodStart, periodEnd, overviewPayload);
    return calculation ? calculation.value : null;
  }

  function calculateMeterConsumption(meterId, periodStart, periodEnd, overviewPayload) {
    if (!meterId || !periodStart || !periodEnd) {
      return null;
    }
    const readings = ((overviewPayload && overviewPayload.meter_readings) || []).filter(function (reading) {
      return String(reading.meter_id) === String(meterId);
    });
    if (readings.length < 2) {
      return null;
    }
    const startReading = interpolateReading(readings, periodStart);
    const inclusiveEnd = formatIsoDate(addUtcDays(parseIsoDate(periodEnd), 1));
    const endReading = interpolateReading(readings, inclusiveEnd);
    if (
      startReading === null ||
      endReading === null ||
      endReading.value < startReading.value
    ) {
      return null;
    }
    return {
      value: endReading.value - startReading.value,
      isInterpolated: startReading.isInterpolated || endReading.isInterpolated,
    };
  }

  function formatMonthLabel(date) {
    return String(date.getUTCMonth() + 1).padStart(2, "0") + "/" + String(date.getUTCFullYear()).slice(-2);
  }

  function formatYearLabel(date) {
    return String(date.getUTCFullYear());
  }

  function buildMeterPeriods(readings, granularity, rangeStart, rangeEnd) {
    if (!readings.length) {
      return [];
    }

    const chartStartDate = parseIsoDate(rangeStart || readings[0].reading_date);
    const chartEndDate = parseIsoDate(rangeEnd || readings[readings.length - 1].reading_date);
    if (chartStartDate > chartEndDate) {
      return [];
    }

    const periods = [];
    if (granularity === "years") {
      for (let year = chartStartDate.getUTCFullYear(); year <= chartEndDate.getUTCFullYear(); year += 1) {
        const yearDate = new Date(Date.UTC(year, 0, 1));
        const yearEnd = new Date(Date.UTC(year, 11, 31));
        const periodEnd = yearEnd > chartEndDate ? chartEndDate : yearEnd;
        periods.push({
          key: formatYearLabel(yearDate) + "-" + formatIsoDate(periodEnd),
          label: formatYearLabel(yearDate),
          end_date: formatIsoDate(periodEnd),
          end: periodEnd.getTime(),
        });
      }
      return periods;
    }

    let monthDate = new Date(Date.UTC(chartStartDate.getUTCFullYear(), chartStartDate.getUTCMonth(), 1));
    while (monthDate <= chartEndDate) {
      const monthEnd = new Date(Date.UTC(monthDate.getUTCFullYear(), monthDate.getUTCMonth() + 1, 0));
      const periodEnd = monthEnd > chartEndDate ? chartEndDate : monthEnd;
      periods.push({
        key:
          String(monthDate.getUTCFullYear()) +
          "-" +
          String(monthDate.getUTCMonth() + 1).padStart(2, "0") +
          "-" +
          formatIsoDate(periodEnd),
        label: formatMonthLabel(monthDate),
        end_date: formatIsoDate(periodEnd),
        end: periodEnd.getTime(),
      });
      monthDate = new Date(Date.UTC(monthDate.getUTCFullYear(), monthDate.getUTCMonth() + 1, 1));
    }
    return periods;
  }

  function normalizeMeterReadings(readings) {
    return readings.map(function (reading) {
      return {
        id: reading.id,
        timestamp: parseIsoDate(reading.reading_date).getTime(),
        reading_date: reading.reading_date,
        value: Number(reading.reading_value),
      };
    });
  }

  function linearInterpolation(startPoint, endPoint, targetTimestamp) {
    const totalDistance = endPoint.timestamp - startPoint.timestamp;
    if (totalDistance === 0) {
      return startPoint.value;
    }
    const factor = (targetTimestamp - startPoint.timestamp) / totalDistance;
    return startPoint.value + factor * (endPoint.value - startPoint.value);
  }

  function quadraticInterpolation(points, targetTimestamp) {
    const origin = points[0].timestamp;
    const targetX = (targetTimestamp - origin) / 86400000;
    const xs = points.map(function (point) {
      return (point.timestamp - origin) / 86400000;
    });
    const ys = points.map(function (point) {
      return point.value;
    });
    let estimate = 0;

    for (let index = 0; index < 3; index += 1) {
      let basis = 1;
      for (let innerIndex = 0; innerIndex < 3; innerIndex += 1) {
        if (innerIndex === index) {
          continue;
        }
        basis *= (targetX - xs[innerIndex]) / (xs[index] - xs[innerIndex]);
      }
      estimate += ys[index] * basis;
    }
    return estimate;
  }

  function estimateInterpolatedReading(normalizedReadings, targetTimestamp, interpolationMode) {
    if (!normalizedReadings.length) {
      return { value: null, source_type: "interpolated" };
    }

    if (targetTimestamp < normalizedReadings[0].timestamp) {
      return { value: null, source_type: "interpolated" };
    }
    if (targetTimestamp >= normalizedReadings[normalizedReadings.length - 1].timestamp) {
      const lastPoint = normalizedReadings[normalizedReadings.length - 1];
      return {
        value: lastPoint.value,
        source_type: targetTimestamp === lastPoint.timestamp ? "recorded" : "interpolated",
      };
    }

    let previousIndex = -1;
    let nextIndex = -1;
    for (let index = 0; index < normalizedReadings.length; index += 1) {
      const point = normalizedReadings[index];
      if (point.timestamp === targetTimestamp) {
        return { value: point.value, source_type: "recorded" };
      }
      if (point.timestamp < targetTimestamp) {
        previousIndex = index;
        continue;
      }
      if (point.timestamp > targetTimestamp) {
        nextIndex = index;
        break;
      }
    }

    if (previousIndex === -1 || nextIndex === -1) {
      return { value: null, source_type: "interpolated" };
    }

    const previousPoint = normalizedReadings[previousIndex];
    const nextPoint = normalizedReadings[nextIndex];
    const lowerBound = Math.min(previousPoint.value, nextPoint.value);
    const upperBound = Math.max(previousPoint.value, nextPoint.value);
    let estimate = linearInterpolation(previousPoint, nextPoint, targetTimestamp);

    if (interpolationMode === "quadratic") {
      const thirdPoint =
        previousIndex > 0
          ? normalizedReadings[previousIndex - 1]
          : nextIndex < normalizedReadings.length - 1
            ? normalizedReadings[nextIndex + 1]
            : null;
      if (thirdPoint) {
        estimate = quadraticInterpolation(
          [thirdPoint, previousPoint, nextPoint].sort(function (left, right) {
            return left.timestamp - right.timestamp;
          }),
          targetTimestamp
        );
      }
    }

    return {
      value: Math.min(Math.max(estimate, lowerBound), upperBound),
      source_type: "interpolated",
    };
  }

  function buildMeterChartSeries(
    readings,
    granularity,
    chartMode,
    interpolationMode,
    rangeStart,
    rangeEnd
  ) {
    const periods = buildMeterPeriods(readings, granularity, rangeStart, rangeEnd);
    if (!periods.length) {
      return [];
    }

    const normalizedReadings = normalizeMeterReadings(readings);
    const effectiveRangeStart = rangeStart || readings[0].reading_date;
    const rangeStartTimestamp = parseIsoDate(effectiveRangeStart).getTime();
    const rangeStartEstimate = estimateInterpolatedReading(
      normalizedReadings,
      rangeStartTimestamp,
      interpolationMode
    );
    const rangeStartPoint = {
      label: effectiveRangeStart,
      timestamp: rangeStartTimestamp,
      date: effectiveRangeStart,
      value: rangeStartEstimate.value,
      source_type: rangeStartEstimate.source_type,
    };
    const cumulativeSeries = periods.map(function (period) {
      const estimatedPoint = estimateInterpolatedReading(
        normalizedReadings,
        period.end,
        interpolationMode
      );
      return {
        label: period.label,
        timestamp: period.end,
        date: period.end_date,
        value: estimatedPoint.value,
        source_type: estimatedPoint.source_type,
      };
    });
    const withRangeStartSeries =
      cumulativeSeries.length && rangeStartPoint.timestamp < cumulativeSeries[0].timestamp
        ? [rangeStartPoint].concat(cumulativeSeries)
        : cumulativeSeries;

    if (chartMode === "bars") {
      const barSource = [rangeStartPoint].concat(cumulativeSeries);
      return cumulativeSeries.map(function (point, index) {
        const previousValue = barSource[index].value;
        return {
          label: point.label,
          timestamp: point.timestamp,
          date: point.date,
          value:
            point.value == null || previousValue == null
              ? 0
              : Math.max(point.value - previousValue, 0),
          source_type: point.source_type,
        };
      });
    }

    return withRangeStartSeries;
  }

  function buildMeterConsumptionSummary(
    readings,
    granularity,
    interpolationMode,
    rangeStart,
    rangeEnd
  ) {
    return buildMeterChartSeries(
      readings,
      granularity,
      "bars",
      interpolationMode,
      rangeStart,
      rangeEnd
    );
  }

  function buildActualMeterReadings(readings, rangeStart, rangeEnd) {
    const rangeStartTime = parseIsoDate(rangeStart).getTime();
    const rangeEndTime = parseIsoDate(rangeEnd).getTime();
    return normalizeMeterReadings(readings)
      .filter(function (point) {
        return point.timestamp >= rangeStartTime && point.timestamp <= rangeEndTime;
      })
      .map(function (point) {
        return {
          label: point.reading_date,
          timestamp: point.timestamp,
          value: point.value,
          source_type: "recorded",
        };
      });
  }

  function formatNumericLabel(value) {
    if (value == null || Number.isNaN(value)) {
      return "-";
    }
    const rounded = Math.round(value * 100) / 100;
    return Number.isInteger(rounded) ? String(rounded) : String(rounded.toFixed(2));
  }

  function addUtcDays(sourceDate, dayDelta) {
    return new Date(
      Date.UTC(
        sourceDate.getUTCFullYear(),
        sourceDate.getUTCMonth(),
        sourceDate.getUTCDate() + dayDelta
      )
    );
  }

  function addUtcMonths(sourceDate, monthDelta) {
    const targetMonthIndex = sourceDate.getUTCFullYear() * 12 + sourceDate.getUTCMonth() + monthDelta;
    const targetYear = Math.floor(targetMonthIndex / 12);
    const targetMonth = targetMonthIndex % 12;
    const daysInTargetMonth = new Date(Date.UTC(targetYear, targetMonth + 1, 0)).getUTCDate();
    return new Date(
      Date.UTC(targetYear, targetMonth, Math.min(sourceDate.getUTCDate(), daysInTargetMonth))
    );
  }

  function resolveExpenseDateRange(expense, openEndedFallbackEnd) {
    if (!expense) {
      return null;
    }
    const hasOneTimeRange =
      expense.charge_type === "one_time" &&
      expense.period_start &&
      expense.period_end &&
      (expense.period_start !== expense.booking_date || expense.period_end !== expense.booking_date);
    const startDateText =
      expense.charge_type === "one_time"
        ? hasOneTimeRange
          ? expense.period_start
          : expense.booking_date || expense.period_start || expense.period_end
        : expense.period_start;
    const endDateText = expense.is_open_ended
      ? openEndedFallbackEnd
      :
      expense.charge_type === "one_time"
        ? hasOneTimeRange
          ? expense.period_end
          : expense.booking_date || expense.period_end || expense.period_start
        : expense.period_end;
    if (!startDateText || !endDateText) {
      return null;
    }
    const startDate = parseIsoDate(startDateText);
    const endDate = parseIsoDate(endDateText);
    if (startDate > endDate) {
      return null;
    }
    return {
      start: startDate,
      end: endDate,
    };
  }

  function calculateOpenEndedRecurringAmount(amount, chargeType, overlapStart, overlapEnd, anchorStart) {
    if (chargeType === "monthly") {
      let total = 0;
      let isInterpolated = false;
      let currentDay = overlapStart;
      while (currentDay <= overlapEnd) {
        const monthEnd = new Date(
          Date.UTC(currentDay.getUTCFullYear(), currentDay.getUTCMonth() + 1, 0)
        );
        const segmentEnd = monthEnd < overlapEnd ? monthEnd : overlapEnd;
        const daysInMonth = monthEnd.getUTCDate();
        const activeDays = Math.floor((segmentEnd - currentDay) / 86400000) + 1;
        total += amount * activeDays / daysInMonth;
        isInterpolated = isInterpolated || activeDays !== daysInMonth;
        currentDay = addUtcDays(segmentEnd, 1);
      }
      return { amount: total, isInterpolated: isInterpolated };
    }

    const cycleMonths = chargeType === "quarterly" ? 3 : 12;
    let cycleStart = anchorStart;
    while (addUtcMonths(cycleStart, cycleMonths) <= overlapStart) {
      cycleStart = addUtcMonths(cycleStart, cycleMonths);
    }

    let total = 0;
    let isInterpolated = false;
    let currentDay = overlapStart;
    while (currentDay <= overlapEnd) {
      const nextCycleStart = addUtcMonths(cycleStart, cycleMonths);
      const cycleEnd = addUtcDays(nextCycleStart, -1);
      const segmentEnd = cycleEnd < overlapEnd ? cycleEnd : overlapEnd;
      const activeDays = Math.floor((segmentEnd - currentDay) / 86400000) + 1;
      const cycleDays = Math.floor((cycleEnd - cycleStart) / 86400000) + 1;
      total += amount * activeDays / cycleDays;
      isInterpolated = isInterpolated || activeDays !== cycleDays;
      currentDay = addUtcDays(segmentEnd, 1);
      cycleStart = nextCycleStart;
    }
    return { amount: total, isInterpolated: isInterpolated };
  }

  function amountForExpenseOverlap(expense, expenseRange, overlapStart, overlapEnd, meterReadings) {
    const calculation = calculateExpenseOverlap(
      expense,
      expenseRange,
      overlapStart,
      overlapEnd,
      meterReadings
    );
    return calculation ? calculation.amount : null;
  }

  function calculateExpenseOverlap(expense, expenseRange, overlapStart, overlapEnd, meterReadings) {
    if (expense.charge_type === "consumption" && expense.meter_id) {
      const meterConsumption = calculateMeterConsumption(
        expense.meter_id,
        formatIsoDate(overlapStart),
        formatIsoDate(overlapEnd),
        { meter_readings: meterReadings || [] }
      );
      const conversionFactor = Number(expense.conversion_factor || "1");
      const unitPrice = Number(expense.amount);
      if (
        meterConsumption !== null &&
        Number.isFinite(conversionFactor) &&
        Number.isFinite(unitPrice)
      ) {
        return {
          amount: unitPrice * meterConsumption.value * conversionFactor,
          isInterpolated: meterConsumption.isInterpolated,
          consumptionValue: meterConsumption.value * conversionFactor,
          consumptionUnit: expense.consumption_unit || expense.meter_unit || "",
        };
      }
      return null;
    }

    if (expense.is_open_ended) {
      const amount = Number(expense.amount);
      if (!Number.isFinite(amount)) {
        return null;
      }
      if (["monthly", "quarterly", "yearly"].indexOf(expense.charge_type) >= 0) {
        const recurringAmount = calculateOpenEndedRecurringAmount(
          amount,
          expense.charge_type,
          overlapStart,
          overlapEnd,
          expenseRange.start
        );
        return {
          amount: recurringAmount.amount,
          isInterpolated: recurringAmount.isInterpolated,
          consumptionValue: null,
          consumptionUnit: "",
        };
      }
    }

    const totalAmount = Number(expense.total_amount);
    if (expense.total_amount == null || expense.total_amount === "" || !Number.isFinite(totalAmount)) {
      return null;
    }
    const expenseDays = Math.floor((expenseRange.end - expenseRange.start) / 86400000) + 1;
    const overlapDays = Math.floor((overlapEnd - overlapStart) / 86400000) + 1;
    return {
      amount: totalAmount * overlapDays / expenseDays,
      isInterpolated:
        overlapStart.getTime() !== expenseRange.start.getTime() ||
        overlapEnd.getTime() !== expenseRange.end.getTime(),
      consumptionValue:
        expense.charge_type === "consumption"
          ? Number(expense.effective_consumption_value || expense.consumption_value || 0)
          : null,
      consumptionUnit: expense.charge_type === "consumption" ? expense.consumption_unit || "" : "",
    };
  }

  function buildExpenseDevelopmentPeriods(granularity, rangeStart, rangeEnd) {
    if (!rangeStart || !rangeEnd) {
      return [];
    }
    const startDate = parseIsoDate(rangeStart);
    const endDate = parseIsoDate(rangeEnd);
    if (startDate > endDate) {
      return [];
    }
    const periods = [];
    let currentStart = startDate;
    while (currentStart <= endDate) {
      const currentPeriodEndCandidate =
        granularity === "years"
          ? new Date(Date.UTC(currentStart.getUTCFullYear(), 11, 31))
          : new Date(Date.UTC(currentStart.getUTCFullYear(), currentStart.getUTCMonth() + 1, 0));
      const currentEnd =
        currentPeriodEndCandidate > endDate ? endDate : currentPeriodEndCandidate;
      periods.push({
        label: granularity === "years" ? formatYearLabel(currentStart) : formatMonthLabel(currentStart),
        start: currentStart,
        end: currentEnd,
      });
      currentStart = addUtcDays(currentEnd, 1);
    }
    return periods;
  }

  function buildExpenseDevelopmentSeries(expenses, meterReadings, granularity, rangeStart, rangeEnd) {
    const periods = buildExpenseDevelopmentPeriods(granularity, rangeStart, rangeEnd);
    if (!periods.length) {
      return [];
    }

    const series = periods.map(function (period) {
      return {
        label: period.label,
        value: 0,
      };
    });

    (expenses || []).forEach(function (expense) {
      const expenseRange = resolveExpenseDateRange(expense, rangeEnd);
      if (!expenseRange) {
        return;
      }
      periods.forEach(function (period, index) {
        const overlapStart = period.start > expenseRange.start ? period.start : expenseRange.start;
        const overlapEnd = period.end < expenseRange.end ? period.end : expenseRange.end;
        if (overlapStart > overlapEnd) {
          return;
        }
        const overlapAmount = amountForExpenseOverlap(
          expense,
          expenseRange,
          overlapStart,
          overlapEnd,
          meterReadings
        );
        if (overlapAmount !== null) {
          series[index].value += overlapAmount;
        }
      });
    });

    return series.map(function (item) {
      return {
        label: item.label,
        value: Number(item.value.toFixed(2)),
      };
    });
  }

  function buildExpenseDevelopmentCompositionSeries(
    expenses,
    meterReadings,
    granularity,
    rangeStart,
    rangeEnd
  ) {
    const periods = buildExpenseDevelopmentPeriods(granularity, rangeStart, rangeEnd);
    if (!periods.length) {
      return [];
    }

    const valuesByCategory = {};
    (expenses || []).forEach(function (expense) {
      const expenseRange = resolveExpenseDateRange(expense, rangeEnd);
      if (!expenseRange) {
        return;
      }
      const categoryName = String(expense.expense_category || "").trim() || "Sonstige";
      if (!valuesByCategory[categoryName]) {
        valuesByCategory[categoryName] = periods.map(function () {
          return 0;
        });
      }

      periods.forEach(function (period, index) {
        const overlapStart = period.start > expenseRange.start ? period.start : expenseRange.start;
        const overlapEnd = period.end < expenseRange.end ? period.end : expenseRange.end;
        if (overlapStart > overlapEnd) {
          return;
        }
        const overlapAmount = amountForExpenseOverlap(
          expense,
          expenseRange,
          overlapStart,
          overlapEnd,
          meterReadings
        );
        if (overlapAmount !== null) {
          valuesByCategory[categoryName][index] += overlapAmount;
        }
      });
    });

    return Object.keys(valuesByCategory)
      .sort(function (left, right) {
        return left.localeCompare(right);
      })
      .map(function (categoryName) {
        return {
          name: categoryName,
          data: valuesByCategory[categoryName].map(function (value) {
            return Number(value.toFixed(2));
          }),
        };
      });
  }

  function buildExpenseCategoryPeriodTotals(expenses, meterReadings, rangeStart, rangeEnd) {
    if (!rangeStart || !rangeEnd) {
      return [];
    }
    const selectedStart = parseIsoDate(rangeStart);
    const selectedEnd = parseIsoDate(rangeEnd);
    if (selectedStart > selectedEnd) {
      return [];
    }

    const totalsByCategory = {};
    (expenses || []).forEach(function (expense) {
      if (expense.is_archived) {
        return;
      }
      const expenseRange = resolveExpenseDateRange(expense, rangeEnd);
      if (!expenseRange) {
        return;
      }
      const overlapStart = selectedStart > expenseRange.start ? selectedStart : expenseRange.start;
      const overlapEnd = selectedEnd < expenseRange.end ? selectedEnd : expenseRange.end;
      if (overlapStart > overlapEnd) {
        return;
      }

      const category = String(expense.expense_category || expense.label || "Nicht kategorisiert");
      if (!totalsByCategory[category]) {
        totalsByCategory[category] = {
          total: 0,
          hasUncalculatedExpense: false,
          hasInterpolatedExpense: false,
          items: [],
        };
      }
      const calculation = calculateExpenseOverlap(
        expense,
        expenseRange,
        overlapStart,
        overlapEnd,
        meterReadings
      );
      if (calculation === null) {
        totalsByCategory[category].hasUncalculatedExpense = true;
        totalsByCategory[category].items.push({
          id: expense.id,
          label: expense.label || expense.expense_category || "Kostenposten",
          beneficiary_name: expense.beneficiary_name,
          amount: null,
          isInterpolated: false,
          consumptionValue: null,
          consumptionUnit: "",
        });
        return;
      }
      totalsByCategory[category].total += calculation.amount;
      totalsByCategory[category].hasInterpolatedExpense =
        totalsByCategory[category].hasInterpolatedExpense || calculation.isInterpolated;
      totalsByCategory[category].items.push({
        id: expense.id,
        label: expense.label || expense.expense_category || "Kostenposten",
        beneficiary_name: expense.beneficiary_name,
        amount: Number(calculation.amount.toFixed(2)),
        isInterpolated: calculation.isInterpolated,
        consumptionValue: calculation.consumptionValue,
        consumptionUnit: calculation.consumptionUnit,
      });
    });

    return Object.keys(totalsByCategory)
      .sort(function (left, right) {
        return left.localeCompare(right, "de");
      })
      .map(function (category) {
        return {
          category: category,
          total: Number(totalsByCategory[category].total.toFixed(2)),
          hasUncalculatedExpense: totalsByCategory[category].hasUncalculatedExpense,
          hasInterpolatedExpense: totalsByCategory[category].hasInterpolatedExpense,
          items: totalsByCategory[category].items,
        };
      });
  }

  function App() {
    const [overview, setOverview] = useState(null);
    const [settlement, setSettlement] = useState(null);
    const [settlementFilters, setSettlementFilters] = useState({ property_id: "", unit_id: "", period_start: bootstrap.settlementPeriodStart, period_end: bootstrap.settlementPeriodEnd });
    const [depreciation, setDepreciation] = useState(null);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [mainTab, setMainTab] = useState("overview");
    const [activeTab, setActiveTab] = useState("properties");
    const [selectedMeterId, setSelectedMeterId] = useState("");
    const [editingExpenseId, setEditingExpenseId] = useState("");
    const [expenseEditForm, setExpenseEditForm] = useState(createExpenseFormState());
    const [expenseListFilters, setExpenseListFilters] = useState({
      year: String(new Date().getFullYear()),
      target: "",
      expense_category: "",
    });
    const [managementListFilters, setManagementListFilters] = useState({
      objects: "",
      properties: "",
      buildings: "",
      units: "",
      rooms: "",
      tenants: "",
      leases: "",
    });
    const [createFormVisibility, setCreateFormVisibility] = useState({
      properties: false,
      buildings: false,
      units: false,
      rooms: false,
      meters: false,
      costs: false,
      tenants: false,
      leases: false,
    });
    const [previewVisibility, setPreviewVisibility] = useState({
      costs: true,
    });
    const [editingEntityIds, setEditingEntityIds] = useState({
      properties: "",
      buildings: "",
      units: "",
      rooms: "",
      tenants: "",
      leases: "",
      meters: "",
    });
    const [meterChartGranularity, setMeterChartGranularity] = useState("months");
    const [meterChartMode, setMeterChartMode] = useState("cumulative");
    const [meterInterpolationMode, setMeterInterpolationMode] = useState("linear");
    const [meterChartRange, setMeterChartRange] = useState(
      buildDefaultMeterChartRange([])
    );
    const [expenseChartConfig, setExpenseChartConfig] = useState({
      from: bootstrap.settlementPeriodStart,
      to: bootstrap.settlementPeriodEnd,
      granularity: "months",
      mode: "bars",
      include_archived: false,
    });
    const [serverStatus, setServerStatus] = useState({
      status: "unknown",
      reachable: false,
      checked_at: null,
    });
    const [paperlessStatus, setPaperlessStatus] = useState({
      configured: false,
      reachable: false,
      message: "Paperless ist nicht konfiguriert.",
      checked_at: null,
    });
    const [paperlessSettings, setPaperlessSettings] = useState({
      base_url: "",
      token_present: false,
      token_masked: null,
      updated_at: null,
    });
    const [applicationSettings, setApplicationSettings] = useState({
      show_delete_actions: true,
      updated_at: null,
    });
    const [paperlessForm, setPaperlessForm] = useState({
      base_url: "",
      api_token: "",
    });
    const [applicationSettingsForm, setApplicationSettingsForm] = useState({
      show_delete_actions: true,
    });
    const [applicationImportFile, setApplicationImportFile] = useState(null);
    const [applicationImportFileName, setApplicationImportFileName] = useState("");
    const [applicationImportInputKey, setApplicationImportInputKey] = useState(0);
    const [expenseDocuments, setExpenseDocuments] = useState([]);
    const [expenseUploadFiles, setExpenseUploadFiles] = useState([]);
    const [expenseDocumentReferenceId, setExpenseDocumentReferenceId] = useState("");
    const [expenseUploadInputKey, setExpenseUploadInputKey] = useState(0);
    const [managementDocuments, setManagementDocuments] = useState([]);
    const [managementUploadFiles, setManagementUploadFiles] = useState([]);
    const [managementDocumentReferenceId, setManagementDocumentReferenceId] = useState("");
    const [managementUploadInputKey, setManagementUploadInputKey] = useState(0);
    const [error, setError] = useState("");
    const [status, setStatus] = useState("");
    const [forms, setForms] = useState({
      property: {
        organization_id: "1",
        name: "",
        street: "",
        city: "",
        postal_code: "",
      },
      building: {
        property_id: "",
        name: "",
        year_built: "",
        street: "",
        city: "",
        postal_code: "",
      },
      unit: {
        building_id: "",
        label: "",
        area_sqm: "",
        room_count: "1",
        street: "",
        city: "",
        postal_code: "",
      },
      room: {
        unit_id: "",
        label: "",
        area_sqm: "",
      },
      meter: {
        object_type: "unit",
        object_id: "",
        label: "",
        meter_type: "",
        unit: "",
        serial_number: "",
      },
      meterReading: {
        meter_id: "",
        reading_date: bootstrap.settlementPeriodEnd,
        reading_value: "",
      },
      tenant: {
        full_name: "",
        email: "",
        phone: "",
        alternate_street: "",
        alternate_postal_code: "",
        alternate_city: "",
      },
      lease: {
        unit_id: "",
        room_id: "",
        tenant_id: "",
        rent_cold: "",
        additional_charges_advance: "",
        occupant_count: "1",
        start_date: bootstrap.settlementPeriodStart,
        end_date: "",
        status: "active",
      },
      expense: {
        object_type: createExpenseFormState().object_type,
        object_id: createExpenseFormState().object_id,
        expense_category: createExpenseFormState().expense_category,
        beneficiary_name: createExpenseFormState().beneficiary_name,
        amount: createExpenseFormState().amount,
        allocation_method: createExpenseFormState().allocation_method,
        charge_type: createExpenseFormState().charge_type,
        interval: createExpenseFormState().interval,
        booking_date: createExpenseFormState().booking_date,
        one_time_period_enabled: createExpenseFormState().one_time_period_enabled,
        period_start: createExpenseFormState().period_start,
        period_end: createExpenseFormState().period_end,
        meter_id: createExpenseFormState().meter_id,
        consumption_unit: createExpenseFormState().consumption_unit,
        consumption_value: createExpenseFormState().consumption_value,
        conversion_factor: createExpenseFormState().conversion_factor,
      },
    });

    function syncFormDefaults(overviewPayload) {
      const firstProperty = (overviewPayload.properties || []).find(function (property) {
        return !property.is_archived;
      });
      const firstBuilding = (overviewPayload.buildings || []).find(function (building) {
        return !building.is_archived;
      });
      const firstUnit = (overviewPayload.units || []).find(function (unit) {
        return !unit.is_archived;
      });
      const firstTenant = (overviewPayload.tenants || [])[0] || null;
      const firstMeter = (overviewPayload.meters || []).find(function (meter) {
        return !meter.is_archived;
      });
      const defaultMeterId =
        (firstMeter && String(firstMeter.id)) ||
        (((overviewPayload.meters || [])[0] && String(overviewPayload.meters[0].id)) || "");
      setForms(function (current) {
        const expenseObjectType = current.expense.object_type || "property";
        const meterObjectType = current.meter.object_type || "unit";
        const hasMeterReadingMeter = (overviewPayload.meters || []).some(function (meter) {
          return String(meter.id) === String(current.meterReading.meter_id || "");
        });
        const hasExpenseMeter = (overviewPayload.meters || []).some(function (meter) {
          return String(meter.id) === String(current.expense.meter_id || "");
        });
        const hasLeaseUnit = (overviewPayload.units || []).some(function (unit) {
          return String(unit.id) === String(current.lease.unit_id || "");
        });
        const activeLeaseRoom = (overviewPayload.rooms || []).find(function (room) {
          return String(room.id) === String(current.lease.room_id || "");
        });
        const hasLeaseRoom = !!activeLeaseRoom;
        const hasLeaseTenant = (overviewPayload.tenants || []).some(function (tenant) {
          return String(tenant.id) === String(current.lease.tenant_id || "");
        });
        const normalizedLeaseUnitId =
          current.lease.unit_id !== "" && hasLeaseUnit
            ? current.lease.unit_id
            : (firstUnit ? String(firstUnit.id) : "");
        const leaseRoomMatchesUnit =
          hasLeaseRoom &&
          String(activeLeaseRoom.unit_id || "") === String(normalizedLeaseUnitId || "");
        return {
          property: {
            organization_id:
              current.property.organization_id ||
              String((firstProperty && firstProperty.organization_id) || 1),
            name: current.property.name,
            street: current.property.street,
            city: current.property.city,
            postal_code: current.property.postal_code,
          },
          building: {
            property_id:
              current.building.property_id !== ""
                ? current.building.property_id
                : (firstProperty ? String(firstProperty.id) : ""),
            name: current.building.name,
            year_built: current.building.year_built,
            street: current.building.street,
            city: current.building.city,
            postal_code: current.building.postal_code,
          },
          unit: {
            building_id:
              current.unit.building_id !== ""
                ? current.unit.building_id
                : (firstBuilding ? String(firstBuilding.id) : ""),
            label: current.unit.label,
            area_sqm: current.unit.area_sqm,
            room_count: current.unit.room_count,
            street: current.unit.street,
            city: current.unit.city,
            postal_code: current.unit.postal_code,
          },
          room: {
            unit_id:
              current.room.unit_id !== ""
                ? current.room.unit_id
                : (firstUnit ? String(firstUnit.id) : ""),
            label: current.room.label,
            area_sqm: current.room.area_sqm,
          },
          meter: {
            object_type: meterObjectType,
            object_id:
              current.meter.object_id !== ""
                ? current.meter.object_id
                : findFirstActiveObjectId(overviewPayload, meterObjectType),
            label: current.meter.label,
            meter_type: current.meter.meter_type,
            unit: current.meter.unit,
            serial_number: current.meter.serial_number,
          },
          meterReading: {
            meter_id:
              current.meterReading.meter_id !== "" && hasMeterReadingMeter
                ? current.meterReading.meter_id
                : defaultMeterId,
            reading_date: current.meterReading.reading_date,
            reading_value: current.meterReading.reading_value,
          },
          tenant: {
            full_name: current.tenant.full_name,
            email: current.tenant.email,
            phone: current.tenant.phone,
            alternate_street: current.tenant.alternate_street,
            alternate_postal_code: current.tenant.alternate_postal_code,
            alternate_city: current.tenant.alternate_city,
          },
          lease: {
            unit_id: normalizedLeaseUnitId,
            room_id:
              current.lease.room_id !== "" && hasLeaseRoom && leaseRoomMatchesUnit
                ? current.lease.room_id
                : "",
            tenant_id:
              current.lease.tenant_id !== "" && hasLeaseTenant
                ? current.lease.tenant_id
                : (firstTenant ? String(firstTenant.id) : ""),
            rent_cold: current.lease.rent_cold,
            additional_charges_advance: current.lease.additional_charges_advance,
            occupant_count: current.lease.occupant_count || "1",
            start_date: current.lease.start_date || bootstrap.settlementPeriodStart,
            end_date: current.lease.end_date,
            status: current.lease.status || "active",
          },
          expense: {
            object_type: expenseObjectType,
            object_id:
              current.expense.object_id !== ""
                ? current.expense.object_id
                : findFirstActiveObjectId(overviewPayload, expenseObjectType),
            expense_category: current.expense.expense_category,
            beneficiary_name: current.expense.beneficiary_name,
            amount: current.expense.amount,
            allocation_method: current.expense.allocation_method,
            charge_type: current.expense.charge_type,
            interval: current.expense.interval,
            booking_date: current.expense.booking_date,
            one_time_period_enabled: current.expense.one_time_period_enabled,
            period_start: current.expense.period_start,
            period_end: current.expense.period_end,
            meter_id:
              current.expense.meter_id !== "" && hasExpenseMeter
                ? current.expense.meter_id
                : "",
            consumption_unit: current.expense.consumption_unit,
            consumption_value: current.expense.consumption_value,
            conversion_factor: current.expense.conversion_factor,
          },
        };
      });
      const hasSelectedMeter = (overviewPayload.meters || []).some(function (meter) {
        return String(meter.id) === String(selectedMeterId || "");
      });
      const nextSelectedMeterId = hasSelectedMeter ? String(selectedMeterId || "") : defaultMeterId;
      setSelectedMeterId(nextSelectedMeterId);
      const nextReadings = (overviewPayload.meter_readings || [])
        .filter(function (reading) {
          return String(reading.meter_id) === String(nextSelectedMeterId);
        })
        .sort(function (left, right) {
          if (left.reading_date === right.reading_date) {
            return Number(left.id) - Number(right.id);
          }
          return left.reading_date < right.reading_date ? -1 : 1;
        });
      setMeterChartRange(buildDefaultMeterChartRange(nextReadings));
    }

    function loadDashboard(nextPropertyId) {
      setLoading(true);
      setError("");
      return fetchJson("/api/health")
        .then(function (healthPayload) {
          setServerStatus(healthPayload);
          return fetchJson("/api/overview");
        })
        .then(function (overviewPayload) {
          const requestedProperty = (overviewPayload.properties || []).find(function (property) {
            return !property.is_archived && String(property.id) === String(nextPropertyId || "");
          });
          const activeProperty = (overviewPayload.properties || []).find(function (property) {
            return !property.is_archived;
          });
          const fallbackPropertyId =
            (requestedProperty && String(requestedProperty.id)) ||
            (activeProperty && String(activeProperty.id)) ||
            "";
          const fallbackUnit = (overviewPayload.units || []).find(function (unit) {
            return !unit.is_archived && !unit.property_id;
          });
          const fallbackUnitId = fallbackPropertyId === "" && fallbackUnit ? String(fallbackUnit.id) : "";

          return Promise.all([
            Promise.resolve(overviewPayload),
            fetchJson(
              "/api/settlements?" +
                new URLSearchParams({
                  property_id: fallbackPropertyId,
                  unit_id: fallbackUnitId,
                  period_start: bootstrap.settlementPeriodStart,
                  period_end: bootstrap.settlementPeriodEnd,
                }).toString()
            ),
            fetchJson(
              "/api/depreciation-schedule?" +
                new URLSearchParams({
                  year: String(bootstrap.depreciationYear),
                }).toString()
            ),
            fetchJson("/api/paperless-settings"),
            fetchJson("/api/paperless-status"),
            fetchJson("/api/application-settings"),
          ]);
        })
        .then(function (results) {
          setOverview(results[0]);
          setSettlement(results[1]);
          setSettlementFilters({
            property_id: results[1].property_id == null ? "" : String(results[1].property_id),
            unit_id: results[1].unit_id == null ? "" : String(results[1].unit_id),
            period_start: bootstrap.settlementPeriodStart,
            period_end: bootstrap.settlementPeriodEnd,
          });
          setDepreciation(results[2]);
          setPaperlessSettings(results[3]);
          setPaperlessStatus(results[4]);
          setApplicationSettings(results[5]);
          setPaperlessForm({
            base_url: (results[3] && results[3].base_url) || "",
            api_token: "",
          });
          setApplicationSettingsForm({
            show_delete_actions:
              !results[5] || typeof results[5].show_delete_actions === "undefined"
                ? true
                : !!results[5].show_delete_actions,
          });
          syncFormDefaults(results[0]);
        })
        .catch(function (loadError) {
          setServerStatus({
            status: "error",
            reachable: false,
            checked_at: null,
          });
          setError(loadError.message || "Daten konnten nicht geladen werden.");
        })
        .finally(function () {
          setLoading(false);
        });
    }

    function handleSettlementFilterChange(event) {
      const field = event.target.name || "property_id";
      const value = event.target.value;
      setSettlementFilters(function (current) {
        if (field === "settlement_target") {
          const separator = value.indexOf(":");
          const targetType = separator < 0 ? "" : value.slice(0, separator);
          const targetId = separator < 0 ? "" : value.slice(separator + 1);
          return Object.assign({}, current, {
            property_id: targetType === "property" ? targetId : "",
            unit_id: targetType === "unit" ? targetId : "",
          });
        }
        return Object.assign({}, current, { [field]: value });
      });
    }

    function handleSettlementFilterSubmit(event) {
      event.preventDefault();
      setLoading(true);
      setError("");
      fetchJson("/api/settlements?" + new URLSearchParams(settlementFilters).toString())
        .then(setSettlement)
        .catch(function (loadError) { setError(loadError.message || "Abrechnung konnte nicht geladen werden."); })
        .finally(function () { setLoading(false); });
    }

    useEffect(function () {
      loadDashboard("");
    }, []);

    function setFormField(formName, field, value) {
      setForms(function (current) {
        return Object.assign({}, current, {
          [formName]: Object.assign({}, current[formName], {
            [field]: value,
          }),
        });
      });
    }

    function setUnitBuildingId(value) {
      const building = (overview && overview.buildings ? overview.buildings : []).find(function (entry) {
        return String(entry.id) === String(value);
      });
      setForms(function (current) {
        return Object.assign({}, current, {
          unit: Object.assign({}, current.unit, {
            building_id: value,
            street: building ? building.street || "" : "",
            city: building ? building.city || "" : "",
            postal_code: building ? building.postal_code || "" : "",
          }),
        });
      });
    }

    function setLeaseUnitId(value) {
      setForms(function (current) {
        const selectedRoom = (overview && overview.rooms ? overview.rooms : []).find(function (room) {
          return String(room.id) === String(current.lease.room_id || "");
        });
        return Object.assign({}, current, {
          lease: Object.assign({}, current.lease, {
            unit_id: value,
            room_id:
              selectedRoom && String(selectedRoom.unit_id || "") === String(value || "")
                ? current.lease.room_id
                : "",
          }),
        });
      });
    }

    function setLeaseRoomId(value) {
      setForms(function (current) {
        const selectedRoom = (overview && overview.rooms ? overview.rooms : []).find(function (room) {
          return String(room.id) === String(value || "");
        });
        return Object.assign({}, current, {
          lease: Object.assign({}, current.lease, {
            room_id: value,
            unit_id: selectedRoom ? String(selectedRoom.unit_id || "") : current.lease.unit_id,
          }),
        });
      });
    }

    function setManagementListFilter(tabKey, value) {
      setManagementListFilters(function (current) {
        return Object.assign({}, current, {
          [tabKey]: value,
        });
      });
    }

    function setCreateFormVisible(tabKey, isVisible) {
      setCreateFormVisibility(function (current) {
        return Object.assign({}, current, {
          [tabKey]: isVisible,
        });
      });
    }

    function clearEditingForTab(tabKey) {
      setEditingEntityIds(function (current) {
        return Object.assign({}, current, {
          [tabKey]: "",
        });
      });
    }

    function resetApplicationImportSelection() {
      setApplicationImportFile(null);
      setApplicationImportFileName("");
      setApplicationImportInputKey(function (current) {
        return current + 1;
      });
    }

    function activateObjectEdit(tabKey, entityId) {
      setActiveTab(tabKey);
      setEditingEntityIds(function (current) {
        return Object.assign({}, current, {
          properties: "",
          buildings: "",
          units: "",
          rooms: "",
          meters: "",
          [tabKey]: String(entityId),
        });
      });
      setCreateFormVisibility(function (current) {
        return Object.assign({}, current, {
          properties: false,
          buildings: false,
          units: false,
          rooms: false,
        });
      });
    }

    function setExpenseTargetValue(targetValue) {
      const parsedTarget = parseObjectTargetValue(targetValue);
      if (!parsedTarget) {
        return;
      }
      const currentMeter = ((overview && overview.meters) || []).find(function (meter) {
        return String(meter.id) === String(forms.expense.meter_id);
      });
      setForms(function (current) {
        return Object.assign({}, current, {
          expense: Object.assign({}, current.expense, {
            object_type: parsedTarget.object_type,
            object_id: parsedTarget.object_id,
            meter_id:
              currentMeter &&
              String(currentMeter.object_type) === String(parsedTarget.object_type) &&
              String(currentMeter.object_id) === String(parsedTarget.object_id)
                ? current.expense.meter_id
                : "",
          }),
        });
      });
    }

    function setExpenseEditField(field, value) {
      setExpenseEditForm(function (current) {
        return Object.assign({}, current, {
          [field]: value,
        });
      });
    }

    function setPaperlessField(field, value) {
      setPaperlessForm(function (current) {
        return Object.assign({}, current, {
          [field]: value,
        });
      });
    }

    function setApplicationSettingsField(field, value) {
      setApplicationSettingsForm(function (current) {
        return Object.assign({}, current, {
          [field]: value,
        });
      });
    }

    function findExpenseCategorySuggestion(expenseCategory) {
      const normalizedCategory = String(expenseCategory || "").trim().toLowerCase();
      if (!normalizedCategory) {
        return null;
      }
      return (overview.expense_categories || []).find(function (category) {
        return String(category.expense_category || "").trim().toLowerCase() === normalizedCategory;
      }) || null;
    }

    function setExpenseCategoryValue(expenseCategory) {
      const matchedCategory = findExpenseCategorySuggestion(expenseCategory);
      setForms(function (current) {
        return Object.assign({}, current, {
          expense: Object.assign({}, current.expense, {
            expense_category: expenseCategory,
            beneficiary_name:
              current.expense.beneficiary_name || !matchedCategory
                ? current.expense.beneficiary_name
                : matchedCategory.beneficiary_name,
          }),
        });
      });
    }

    function setExpenseEditCategoryValue(expenseCategory) {
      const matchedCategory = findExpenseCategorySuggestion(expenseCategory);
      setExpenseEditForm(function (current) {
        return Object.assign({}, current, {
          expense_category: expenseCategory,
          beneficiary_name:
            current.beneficiary_name || !matchedCategory
              ? current.beneficiary_name
              : matchedCategory.beneficiary_name,
        });
      });
    }

    function setExpenseEditTargetValue(targetValue) {
      const parsedTarget = parseObjectTargetValue(targetValue);
      if (!parsedTarget) {
        return;
      }
      const currentMeter = ((overview && overview.meters) || []).find(function (meter) {
        return String(meter.id) === String(expenseEditForm.meter_id);
      });
      setExpenseEditForm(function (current) {
        return Object.assign({}, current, {
          object_type: parsedTarget.object_type,
          object_id: parsedTarget.object_id,
          meter_id:
            currentMeter &&
            String(currentMeter.object_type) === String(parsedTarget.object_type) &&
            String(currentMeter.object_id) === String(parsedTarget.object_id)
              ? current.meter_id
              : "",
        });
      });
    }

    function setMeterObjectType(objectType) {
      setForms(function (current) {
        return Object.assign({}, current, {
          meter: Object.assign({}, current.meter, {
            object_type: objectType,
            object_id: findFirstActiveObjectId(overview || {}, objectType),
          }),
        });
      });
    }

    function setExpenseMeterId(meterId) {
      setForms(function (current) {
        const selectedMeter = ((overview && overview.meters) || []).find(function (meter) {
          return String(meter.id) === String(meterId);
        });
        return Object.assign({}, current, {
          expense: Object.assign({}, current.expense, {
            meter_id: meterId,
            consumption_unit: selectedMeter ? selectedMeter.unit : current.expense.consumption_unit,
            consumption_value: selectedMeter ? "" : current.expense.consumption_value,
            conversion_factor:
              selectedMeter && current.expense.consumption_unit !== "" &&
              current.expense.consumption_unit !== selectedMeter.unit
                ? current.expense.conversion_factor
                : "",
          }),
        });
      });
    }

    function setExpenseEditMeterId(meterId) {
      setExpenseEditForm(function (current) {
        const selectedMeter = ((overview && overview.meters) || []).find(function (meter) {
          return String(meter.id) === String(meterId);
        });
        return Object.assign({}, current, {
          meter_id: meterId,
          consumption_unit: selectedMeter ? selectedMeter.unit : current.consumption_unit,
          consumption_value: selectedMeter ? "" : current.consumption_value,
          conversion_factor:
            selectedMeter && current.consumption_unit !== "" &&
            current.consumption_unit !== selectedMeter.unit
              ? current.conversion_factor
              : "",
        });
      });
    }

    function setActiveMeterSelection(meterId) {
      const nextMeterId = meterId ? String(meterId) : "";
      setSelectedMeterId(nextMeterId);
      const nextReadings = ((overview && overview.meter_readings) || [])
        .filter(function (reading) {
          return String(reading.meter_id) === nextMeterId;
        })
        .sort(function (left, right) {
          if (left.reading_date === right.reading_date) {
            return Number(left.id) - Number(right.id);
          }
          return left.reading_date < right.reading_date ? -1 : 1;
        });
      setMeterChartRange(buildDefaultMeterChartRange(nextReadings));
      setForms(function (current) {
        return Object.assign({}, current, {
          meterReading: Object.assign({}, current.meterReading, {
            meter_id: nextMeterId,
          }),
        });
      });
    }

    function setMeterChartRangeBoundary(boundary, value) {
      setMeterChartRange(function (current) {
        const nextRange = Object.assign({}, current, {
          [boundary]: value,
        });
        if (!nextRange.from || !nextRange.to) {
          return nextRange;
        }
        if (nextRange.from > nextRange.to) {
          if (boundary === "from") {
            return {
              from: nextRange.from,
              to: nextRange.from,
            };
          }
          return {
            from: nextRange.to,
            to: nextRange.to,
          };
        }
        return nextRange;
      });
    }

    function setExpenseChartRangeBoundary(boundary, value) {
      setExpenseChartConfig(function (current) {
        const nextConfig = Object.assign({}, current, {
          [boundary]: value,
        });
        if (!nextConfig.from || !nextConfig.to) {
          return nextConfig;
        }
        if (nextConfig.from > nextConfig.to) {
          if (boundary === "from") {
            return Object.assign({}, nextConfig, {
              to: nextConfig.from,
            });
          }
          return Object.assign({}, nextConfig, {
            from: nextConfig.to,
          });
        }
        return nextConfig;
      });
    }

    function resolveExpensePropertyId(objectType, objectIdValue) {
      const objectId = toIntegerOrNull(objectIdValue);
      if (!objectId) {
        return "";
      }
      if (objectType === "property") {
        return String(objectId);
      }
      if (objectType === "building") {
        const building = (overview.buildings || []).find(function (item) {
          return item.id === objectId;
        });
        return building && building.property_id ? String(building.property_id) : "";
      }
      if (objectType === "unit") {
        const unit = (overview.units || []).find(function (item) {
          return item.id === objectId;
        });
        return unit && unit.property_id ? String(unit.property_id) : "";
      }
      if (objectType === "room") {
        const room = (overview.rooms || []).find(function (item) {
          return item.id === objectId;
        });
        return room && room.property_id ? String(room.property_id) : "";
      }
      return "";
    }

    function resetForm(formName, factory) {
      setForms(function (current) {
        return Object.assign({}, current, {
          [formName]: factory(current[formName]),
        });
      });
    }

    function resetExpenseEdit() {
      setEditingExpenseId("");
      setExpenseEditForm(createExpenseFormState());
      setExpenseDocuments([]);
      setExpenseUploadFiles([]);
      setExpenseDocumentReferenceId("");
      setExpenseUploadInputKey(function (current) {
        return current + 1;
      });
    }

    function resetManagementForm(tabKey) {
      if (tabKey === "properties") {
        resetForm("property", function (current) {
          return {
            organization_id: current.organization_id,
            name: "",
            street: "",
            city: "",
            postal_code: "",
          };
        });
        return;
      }
      if (tabKey === "buildings") {
        resetForm("building", function (current) {
          return {
            property_id: current.property_id,
            name: "",
            year_built: "",
            street: "",
            city: "",
            postal_code: "",
          };
        });
        return;
      }
      if (tabKey === "units") {
        resetForm("unit", function (current) {
          return {
            building_id: current.building_id,
            label: "",
            area_sqm: "",
            room_count: "1",
            street: "",
            city: "",
            postal_code: "",
          };
        });
        return;
      }
      if (tabKey === "rooms") {
        resetForm("room", function (current) {
          return {
            unit_id: current.unit_id,
            label: "",
            area_sqm: "",
          };
        });
        return;
      }
      if (tabKey === "tenants") {
        resetForm("tenant", function () {
          return {
            full_name: "",
            email: "",
            phone: "",
          };
        });
        return;
      }
      if (tabKey === "leases") {
        resetForm("lease", function (current) {
          return {
            unit_id: current.unit_id,
            room_id: current.room_id,
            tenant_id: current.tenant_id,
            rent_cold: "",
            additional_charges_advance: "",
            occupant_count: "1",
            start_date: current.start_date || bootstrap.settlementPeriodStart,
            end_date: "",
            status: current.status || "active",
          };
        });
        return;
      }
      if (tabKey === "meters") {
        resetForm("meter", function (current) {
          return {
            object_type: current.object_type || "property",
            object_id: current.object_id || "",
            label: "",
            meter_type: "",
            unit: "",
            serial_number: "",
          };
        });
      }
    }

    function cancelManagementEdit(tabKey) {
      clearEditingForTab(tabKey);
      setCreateFormVisible(tabKey, false);
      resetManagementForm(tabKey);
      if (tabKey === "tenants" || tabKey === "leases") {
        resetManagementDocumentState();
      }
    }

    function openCreateForm(tabKey) {
      setError("");
      setStatus("");
      if (tabKey === "costs") {
        resetExpenseEdit();
        setCreateFormVisible(tabKey, true);
        return;
      }
      if (["properties", "buildings", "units", "rooms", "tenants", "leases", "meters"].indexOf(tabKey) >= 0) {
        cancelManagementEdit(tabKey);
      }
      setCreateFormVisible(tabKey, true);
    }

    function resetManagementDocumentState() {
      setManagementDocuments([]);
      setManagementUploadFiles([]);
      setManagementDocumentReferenceId("");
      setManagementUploadInputKey(function (current) {
        return current + 1;
      });
    }

    function buildManagementDocumentsBasePath(resourcePlural, resourceId) {
      return "/api/" + String(resourcePlural) + "/" + String(resourceId) + "/documents";
    }

    function loadManagementDocuments(resourcePlural, resourceId) {
      return fetchJson(buildManagementDocumentsBasePath(resourcePlural, resourceId)).then(function (payload) {
        setManagementDocuments((payload && payload.documents) || []);
      });
    }

    function loadExpenseDocuments(expenseId) {
      return fetchJson("/api/expenses/" + String(expenseId) + "/documents").then(function (payload) {
        setExpenseDocuments((payload && payload.documents) || []);
      });
    }

    function startExpenseEdit(expense) {
      if (String(editingExpenseId) === String(expense.id)) {
        resetExpenseEdit();
        return;
      }
      setPreviewVisibility(function (current) {
        return Object.assign({}, current, {
          costs: true,
        });
      });
      setEditingExpenseId(String(expense.id));
      setExpenseEditForm(expenseFormFromExpense(expense));
      setExpenseUploadFiles([]);
      setExpenseDocumentReferenceId("");
      setExpenseUploadInputKey(function (current) {
        return current + 1;
      });
      loadExpenseDocuments(expense.id).catch(function (loadError) {
        setError(loadError.message || "Dokumente konnten nicht geladen werden.");
      });
    }

    function handleExpenseDocumentSelection(event) {
      setExpenseUploadFiles(Array.from(event.target.files || []));
    }

    function handleManagementDocumentSelection(event) {
      setManagementUploadFiles(Array.from(event.target.files || []));
    }

    function handleExpenseDocumentReferenceCreate(expenseId) {
      const normalizedDocumentId = String(expenseDocumentReferenceId || "").trim();
      if (normalizedDocumentId === "") {
        return;
      }
      setSaving(true);
      setError("");
      setStatus("");
      fetchJson("/api/expenses/" + String(expenseId) + "/documents", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          documents: [
            {
              paperless_document_id: normalizedDocumentId,
            },
          ],
        }),
      })
        .then(function () {
          setExpenseDocumentReferenceId("");
          setStatus("Dokumenten-ID hinzugefügt.");
          return loadExpenseDocuments(expenseId);
        })
        .catch(function (saveError) {
          setError(saveError.message || "Dokumenten-ID konnte nicht hinzugefügt werden.");
        })
        .finally(function () {
          setSaving(false);
        });
    }

    function handleManagementDocumentReferenceCreate(resourcePlural, resourceId) {
      const normalizedDocumentId = String(managementDocumentReferenceId || "").trim();
      if (normalizedDocumentId === "") {
        return;
      }
      setSaving(true);
      setError("");
      setStatus("");
      fetchJson(buildManagementDocumentsBasePath(resourcePlural, resourceId), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          documents: [
            {
              paperless_document_id: normalizedDocumentId,
            },
          ],
        }),
      })
        .then(function () {
          setManagementDocumentReferenceId("");
          setStatus("Dokumenten-ID hinzugefügt.");
          return loadManagementDocuments(resourcePlural, resourceId);
        })
        .catch(function (saveError) {
          setError(saveError.message || "Dokumenten-ID konnte nicht hinzugefügt werden.");
        })
        .finally(function () {
          setSaving(false);
        });
    }

    function readFileAsUploadPayload(file) {
      return new Promise(function (resolve, reject) {
        const reader = new FileReader();
        reader.onload = function (loadEvent) {
          const rawResult = String(
            (loadEvent && loadEvent.target && loadEvent.target.result) || ""
          );
          const commaIndex = rawResult.indexOf(",");
          const contentBase64 = commaIndex >= 0 ? rawResult.slice(commaIndex + 1) : rawResult;
          if (!contentBase64) {
            reject(new Error("Datei konnte nicht gelesen werden."));
            return;
          }
          resolve({
            filename: file.name,
            content_type: file.type || "application/octet-stream",
            content_base64: contentBase64,
          });
        };
        reader.onerror = function () {
          reject(new Error("Datei konnte nicht gelesen werden."));
        };
        reader.readAsDataURL(file);
      });
    }

    function handleExpenseDocumentUpload(expenseId) {
      if (!expenseUploadFiles.length) {
        return;
      }
      setSaving(true);
      setError("");
      setStatus("");
      Promise.all(
        expenseUploadFiles.map(function (file) {
          return readFileAsUploadPayload(file);
        })
      )
        .then(function (documents) {
          return fetchJson("/api/expenses/" + String(expenseId) + "/documents", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ documents: documents }),
          });
        })
        .then(function () {
          setExpenseUploadFiles([]);
          setExpenseUploadInputKey(function (current) {
            return current + 1;
          });
          setStatus("Dokumente hochgeladen.");
          return loadExpenseDocuments(expenseId);
        })
        .catch(function (saveError) {
          setError(saveError.message || "Dokumente konnten nicht hochgeladen werden.");
        })
        .finally(function () {
          setSaving(false);
        });
    }

    function handleManagementDocumentUpload(resourcePlural, resourceId) {
      if (!managementUploadFiles.length) {
        return;
      }
      setSaving(true);
      setError("");
      setStatus("");
      Promise.all(
        managementUploadFiles.map(function (file) {
          return readFileAsUploadPayload(file);
        })
      )
        .then(function (documents) {
          return fetchJson(buildManagementDocumentsBasePath(resourcePlural, resourceId), {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ documents: documents }),
          });
        })
        .then(function () {
          setManagementUploadFiles([]);
          setManagementUploadInputKey(function (current) {
            return current + 1;
          });
          setStatus("Dokumente hochgeladen.");
          return loadManagementDocuments(resourcePlural, resourceId);
        })
        .catch(function (saveError) {
          setError(saveError.message || "Dokumente konnten nicht hochgeladen werden.");
        })
        .finally(function () {
          setSaving(false);
        });
    }

    function handleExpenseDocumentDelete(expenseId, documentId) {
      setSaving(true);
      setError("");
      setStatus("");
      fetchJson(
        "/api/expenses/" + String(expenseId) + "/documents/" + String(documentId),
        {
          method: "DELETE",
        }
      )
        .then(function () {
          setStatus("Dokument gelöscht.");
          return loadExpenseDocuments(expenseId);
        })
        .catch(function (saveError) {
          setError(saveError.message || "Dokument konnte nicht gelöscht werden.");
        })
        .finally(function () {
          setSaving(false);
        });
    }

    function handleManagementDocumentDelete(resourcePlural, resourceId, documentId) {
      setSaving(true);
      setError("");
      setStatus("");
      fetchJson(
        buildManagementDocumentsBasePath(resourcePlural, resourceId) + "/" + String(documentId),
        { method: "DELETE" }
      )
        .then(function () {
          setStatus("Dokument gelöscht.");
          return loadManagementDocuments(resourcePlural, resourceId);
        })
        .catch(function (saveError) {
          setError(saveError.message || "Dokument konnte nicht gelöscht werden.");
        })
        .finally(function () {
          setSaving(false);
        });
    }

    function submitToApi(url, payload, successMessage, resetCallback, nextPropertyId, method) {
      setSaving(true);
      setError("");
      setStatus("");
      fetchJson(url, {
        method: method || "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      })
        .then(function () {
          setStatus(successMessage);
          resetCallback();
          return loadDashboard(nextPropertyId || "");
        })
        .catch(function (saveError) {
          setError(saveError.message || "Die Daten konnten nicht gespeichert werden.");
        })
        .finally(function () {
          setSaving(false);
        });
    }

    function performObjectAction(url, method, successMessage, nextPropertyId) {
      setSaving(true);
      setError("");
      setStatus("");
      fetchJson(url, { method: method })
        .then(function () {
          setStatus(successMessage);
          return loadDashboard(nextPropertyId || "");
        })
        .catch(function (requestError) {
          setError(requestError.message || "Die Aktion konnte nicht ausgeführt werden.");
        })
        .finally(function () {
          setSaving(false);
        });
    }

    function deleteMeterReading(reading) {
      const url = "/api/meter-readings/" + String(reading.id);
      setSaving(true);
      setError("");
      setStatus("");
      fetchJson(url, { method: "DELETE" })
        .then(function () {
          setStatus("Zählerstand gelöscht.");
          return loadDashboard("");
        })
        .catch(function (requestError) {
          setError(requestError.message || "Der Zählerstand konnte nicht gelöscht werden.");
        })
        .finally(function () {
          setSaving(false);
        });
    }

    function handleTenantDelete(tenantId) {
      const normalizedTenantId = String(tenantId || "");
      if (normalizedTenantId === "") {
        return;
      }
      setSaving(true);
      setError("");
      setStatus("");
      fetchJson("/api/tenants/" + normalizedTenantId, { method: "DELETE" })
        .then(function () {
          cancelManagementEdit("tenants");
          setStatus("Mieter gelöscht.");
          return loadDashboard("");
        })
        .catch(function (requestError) {
          setError(requestError.message || "Der Mieter konnte nicht gelöscht werden.");
        })
        .finally(function () {
          setSaving(false);
        });
    }

    function handleLeaseDelete(leaseId) {
      const normalizedLeaseId = String(leaseId || "");
      if (normalizedLeaseId === "") {
        return;
      }
      setSaving(true);
      setError("");
      setStatus("");
      fetchJson("/api/leases/" + normalizedLeaseId, { method: "DELETE" })
        .then(function () {
          cancelManagementEdit("leases");
          setStatus("Mietvertrag gelöscht.");
          return loadDashboard("");
        })
        .catch(function (requestError) {
          setError(requestError.message || "Der Mietvertrag konnte nicht gelöscht werden.");
        })
        .finally(function () {
          setSaving(false);
        });
    }

    function objectActionCell(resourceName, item, onEdit) {
      const label = formatDisplayName(item);
      if (item.is_archived) {
        return e(
          "td",
          null,
          e(
            "div",
            { className: "inline-actions" },
            e(
              "button",
              {
                type: "button",
                className: "action-button secondary",
                disabled: saving || loading,
                onClick: function (event) {
                  event.stopPropagation();
                  performObjectAction(
                    "/api/" + resourceName + "/" + String(item.id) + "/restore",
                    "POST",
                    label + " wiederhergestellt.",
                    ""
                  );
                },
              },
              "Archivierung aufheben"
            ),
            showDeleteActions
              ? e(
                  "button",
                  {
                    type: "button",
                    className: "action-button danger",
                    disabled: saving || loading,
                    onClick: function (event) {
                      event.stopPropagation();
                      performObjectAction(
                        "/api/" + resourceName + "/" + String(item.id),
                        "DELETE",
                        label + " gelöscht.",
                        ""
                      );
                    },
                  },
                  "Löschen"
                )
              : null
          )
        );
      }

      if (resourceName === "expenses") {
        return e("td", null);
      }

      return e(
        "td",
        null,
        e(
          "div",
          { className: "inline-actions" },
          onEdit
            ? e(
                "button",
                {
                  type: "button",
                  className: "action-button secondary",
                  disabled: saving || loading,
                  onClick: function (event) {
                    event.stopPropagation();
                    onEdit(item);
                  },
                },
                "Bearbeiten"
              )
            : null,
          e(
            "button",
            {
              type: "button",
              className: "action-button secondary",
              disabled: saving || loading,
              onClick: function (event) {
                event.stopPropagation();
                performObjectAction(
                  "/api/" + resourceName + "/" + String(item.id) + "/archive",
                  "POST",
                  label + " archiviert.",
                  ""
                );
              },
            },
            "Archivieren"
          )
        )
      );
    }

    function handlePropertySubmit(event) {
      event.preventDefault();
      const editingId = String(editingEntityIds.properties || "");
      const isEditing = editingId !== "";
      const payload = {
        organization_id: Number(forms.property.organization_id || "1"),
        name: forms.property.name,
        street: forms.property.street,
        city: forms.property.city,
        postal_code: forms.property.postal_code,
      };
      submitToApi(
        isEditing ? "/api/properties/" + editingId : "/api/properties",
        payload,
        isEditing ? "Anlage aktualisiert." : "Anlage gespeichert.",
        function () {
          clearEditingForTab("properties");
          setCreateFormVisible("properties", false);
          resetForm("property", function (current) {
            return {
              organization_id: current.organization_id,
              name: "",
              street: "",
              city: "",
              postal_code: "",
            };
          });
        },
        "",
        isEditing ? "PUT" : "POST"
      );
    }

    function handleBuildingSubmit(event) {
      event.preventDefault();
      const editingId = String(editingEntityIds.buildings || "");
      const isEditing = editingId !== "";
      const payload = {
        property_id: toIntegerOrNull(forms.building.property_id),
        name: forms.building.name,
        year_built: forms.building.year_built ? Number(forms.building.year_built) : null,
        street: forms.building.street,
        city: forms.building.city,
        postal_code: forms.building.postal_code,
      };
      submitToApi(
        isEditing ? "/api/buildings/" + editingId : "/api/buildings",
        payload,
        isEditing ? "Gebäude aktualisiert." : "Gebäude gespeichert.",
        function () {
          clearEditingForTab("buildings");
          setCreateFormVisible("buildings", false);
          resetForm("building", function (current) {
            return {
              property_id: current.property_id,
              name: "",
              year_built: "",
              street: "",
              city: "",
              postal_code: "",
            };
          });
        },
        forms.building.property_id || "",
        isEditing ? "PUT" : "POST"
      );
    }

    function handleUnitSubmit(event) {
      event.preventDefault();
      const editingId = String(editingEntityIds.units || "");
      const isEditing = editingId !== "";
      const payload = {
        building_id: toIntegerOrNull(forms.unit.building_id),
        label: forms.unit.label,
        area_sqm: forms.unit.area_sqm,
        room_count: Number(forms.unit.room_count),
        street: forms.unit.street,
        city: forms.unit.city,
        postal_code: forms.unit.postal_code,
      };
      submitToApi(
        isEditing ? "/api/units/" + editingId : "/api/units",
        payload,
        isEditing ? "Wohnung aktualisiert." : "Wohnung gespeichert.",
        function () {
          clearEditingForTab("units");
          setCreateFormVisible("units", false);
          resetForm("unit", function (current) {
            return {
              building_id: current.building_id,
              label: "",
              area_sqm: "",
              room_count: "1",
              street: "",
              city: "",
              postal_code: "",
            };
          });
        },
        resolveExpensePropertyId("building", forms.unit.building_id),
        isEditing ? "PUT" : "POST"
      );
    }

    function handleRoomSubmit(event) {
      event.preventDefault();
      const editingId = String(editingEntityIds.rooms || "");
      const isEditing = editingId !== "";
      const payload = {
        unit_id: Number(forms.room.unit_id),
        label: forms.room.label,
        area_sqm: forms.room.area_sqm === "" ? null : forms.room.area_sqm,
      };
      submitToApi(
        isEditing ? "/api/rooms/" + editingId : "/api/rooms",
        payload,
        isEditing ? "Zimmer aktualisiert." : "Zimmer gespeichert.",
        function () {
          clearEditingForTab("rooms");
          setCreateFormVisible("rooms", false);
          resetForm("room", function (current) {
            return {
              unit_id: current.unit_id,
              label: "",
              area_sqm: "",
            };
          });
        },
        resolveExpensePropertyId("unit", forms.room.unit_id),
        isEditing ? "PUT" : "POST"
      );
    }

    function handleTenantSubmit(event) {
      event.preventDefault();
      const editingId = String(editingEntityIds.tenants || "");
      const isEditing = editingId !== "";
      const payload = {
        full_name: forms.tenant.full_name,
        email: forms.tenant.email || null,
        phone: forms.tenant.phone || null,
        alternate_street: forms.tenant.alternate_street || null,
        alternate_postal_code: forms.tenant.alternate_postal_code || null,
        alternate_city: forms.tenant.alternate_city || null,
      };
      submitToApi(
        isEditing ? "/api/tenants/" + editingId : "/api/tenants",
        payload,
        isEditing ? "Mieter aktualisiert." : "Mieter gespeichert.",
        function () {
          clearEditingForTab("tenants");
          setCreateFormVisible("tenants", false);
          resetManagementDocumentState();
          resetForm("tenant", function () {
            return {
              full_name: "",
              email: "",
              phone: "",
            };
          });
        },
        "",
        isEditing ? "PUT" : "POST"
      );
    }

    function handleLeaseSubmit(event) {
      event.preventDefault();
      const editingId = String(editingEntityIds.leases || "");
      const isEditing = editingId !== "";
      const payload = {
        unit_id: Number(forms.lease.unit_id),
        room_id: forms.lease.room_id === "" ? null : Number(forms.lease.room_id),
        tenant_id: Number(forms.lease.tenant_id),
        rent_cold: forms.lease.rent_cold,
        additional_charges_advance: forms.lease.additional_charges_advance,
        occupant_count: Number(forms.lease.occupant_count),
        start_date: forms.lease.start_date,
        end_date: forms.lease.end_date || null,
        status: forms.lease.status || "active",
      };
      submitToApi(
        isEditing ? "/api/leases/" + editingId : "/api/leases",
        payload,
        isEditing ? "Mietvertrag aktualisiert." : "Mietvertrag gespeichert.",
        function () {
          clearEditingForTab("leases");
          setCreateFormVisible("leases", false);
          resetManagementDocumentState();
          resetForm("lease", function (current) {
            return {
              unit_id: current.unit_id,
              room_id: current.room_id,
              tenant_id: current.tenant_id,
              rent_cold: "",
              additional_charges_advance: "",
              occupant_count: "1",
              start_date: current.start_date,
              end_date: "",
              status: current.status || "active",
            };
          });
        },
        "",
        isEditing ? "PUT" : "POST"
      );
    }

    function startPropertyEdit(property) {
      if (String(editingEntityIds.properties || "") === String(property.id)) {
        cancelManagementEdit("properties");
        return;
      }
      setError("");
      setStatus("");
      activateObjectEdit("properties", property.id);
      setForms(function (current) {
        return Object.assign({}, current, {
          property: {
            organization_id: String(property.organization_id || "1"),
            name: property.name || "",
            street: property.street || "",
            city: property.city || "",
            postal_code: property.postal_code || "",
          },
        });
      });
    }

    function startBuildingEdit(building) {
      if (String(editingEntityIds.buildings || "") === String(building.id)) {
        cancelManagementEdit("buildings");
        return;
      }
      setError("");
      setStatus("");
      activateObjectEdit("buildings", building.id);
      setForms(function (current) {
        return Object.assign({}, current, {
          building: {
            property_id:
              building.property_id === null || typeof building.property_id === "undefined"
                ? ""
                : String(building.property_id),
            name: building.name || "",
            year_built:
              building.year_built === null || typeof building.year_built === "undefined"
                ? ""
                : String(building.year_built),
            street: building.street || "",
            city: building.city || "",
            postal_code: building.postal_code || "",
          },
        });
      });
    }

    function startUnitEdit(unit) {
      if (String(editingEntityIds.units || "") === String(unit.id)) {
        cancelManagementEdit("units");
        return;
      }
      setError("");
      setStatus("");
      activateObjectEdit("units", unit.id);
      setForms(function (current) {
        return Object.assign({}, current, {
          unit: {
            building_id:
              unit.building_id === null || typeof unit.building_id === "undefined"
                ? ""
                : String(unit.building_id),
            label: unit.label || "",
            area_sqm: unit.area_sqm == null ? "" : String(unit.area_sqm),
            room_count: unit.room_count == null ? "1" : String(unit.room_count),
            street: unit.street || "",
            city: unit.city || "",
            postal_code: unit.postal_code || "",
          },
        });
      });
    }

    function startRoomEdit(room) {
      if (String(editingEntityIds.rooms || "") === String(room.id)) {
        cancelManagementEdit("rooms");
        return;
      }
      setError("");
      setStatus("");
      activateObjectEdit("rooms", room.id);
      setForms(function (current) {
        return Object.assign({}, current, {
          room: {
            unit_id: room.unit_id == null ? "" : String(room.unit_id),
            label: room.label || "",
            area_sqm: room.area_sqm == null ? "" : String(room.area_sqm),
          },
        });
      });
    }

    function startTenantEdit(tenant) {
      if (String(editingEntityIds.tenants || "") === String(tenant.id)) {
        cancelManagementEdit("tenants");
        return;
      }
      setError("");
      setStatus("");
      resetManagementDocumentState();
      setEditingEntityIds(function (current) {
        return Object.assign({}, current, {
          tenants: String(tenant.id),
        });
      });
      setCreateFormVisible("tenants", false);
      setForms(function (current) {
        return Object.assign({}, current, {
          tenant: {
            full_name: tenant.full_name || "",
            email: tenant.email || "",
            phone: tenant.phone || "",
            alternate_street: tenant.alternate_street || "",
            alternate_postal_code: tenant.alternate_postal_code || "",
            alternate_city: tenant.alternate_city || "",
          },
        });
      });
      loadManagementDocuments("tenants", tenant.id).catch(function (loadError) {
        setError(loadError.message || "Dokumente konnten nicht geladen werden.");
      });
    }

    function startLeaseEdit(lease) {
      if (String(editingEntityIds.leases || "") === String(lease.id)) {
        cancelManagementEdit("leases");
        return;
      }
      setError("");
      setStatus("");
      resetManagementDocumentState();
      setEditingEntityIds(function (current) {
        return Object.assign({}, current, {
          leases: String(lease.id),
        });
      });
      setCreateFormVisible("leases", false);
      setForms(function (current) {
        return Object.assign({}, current, {
          lease: {
            unit_id: lease.unit_id == null ? "" : String(lease.unit_id),
            room_id: lease.room_id == null ? "" : String(lease.room_id),
            tenant_id: lease.tenant_id == null ? "" : String(lease.tenant_id),
            rent_cold: lease.rent_cold == null ? "" : String(lease.rent_cold),
            additional_charges_advance:
              lease.additional_charges_advance == null
                ? ""
                : String(lease.additional_charges_advance),
            occupant_count: lease.occupant_count == null ? "1" : String(lease.occupant_count),
            start_date: lease.start_date || bootstrap.settlementPeriodStart,
            end_date: lease.end_date || "",
            status: lease.status || "active",
          },
        });
      });
      loadManagementDocuments("leases", lease.id).catch(function (loadError) {
        setError(loadError.message || "Dokumente konnten nicht geladen werden.");
      });
    }

    function handleMeterSubmit(event) {
      event.preventDefault();
      const editingId = String(editingEntityIds.meters || "");
      const isEditing = editingId !== "";
      const payload = {
        object_type: forms.meter.object_type,
        object_id: Number(forms.meter.object_id),
        label: forms.meter.label,
        meter_type: forms.meter.meter_type || null,
        unit: forms.meter.unit,
        serial_number: forms.meter.serial_number || null,
      };
      submitToApi(
        isEditing ? "/api/meters/" + editingId : "/api/meters",
        payload,
        isEditing ? "Zähler aktualisiert." : "Zähler gespeichert.",
        function () {
          clearEditingForTab("meters");
          setCreateFormVisible("meters", false);
          resetForm("meter", function (current) {
            return {
              object_type: current.object_type,
              object_id: current.object_id,
              label: "",
              meter_type: "",
              unit: "",
              serial_number: "",
            };
          });
        },
        resolveExpensePropertyId(forms.meter.object_type, forms.meter.object_id),
        isEditing ? "PUT" : "POST"
      );
    }

    function startMeterEdit(meter) {
      if (String(editingEntityIds.meters || "") === String(meter.id)) {
        cancelManagementEdit("meters");
        return;
      }
      setError("");
      setStatus("");
      activateObjectEdit("meters", meter.id);
      setForms(function (current) {
        return Object.assign({}, current, {
          meter: {
            object_type: meter.object_type || "property",
            object_id: meter.object_id == null ? "" : String(meter.object_id),
            label: meter.label || "",
            meter_type: meter.meter_type || "",
            unit: meter.unit || "",
            serial_number: meter.serial_number || "",
          },
        });
      });
      setActiveMeterSelection(meter.id);
    }

    function handleMeterReadingSubmit(event) {
      event.preventDefault();
      const meterId = Number(forms.meterReading.meter_id);
      const selectedMeter = (overview.meters || []).find(function (meter) {
        return meter.id === meterId;
      });
      submitToApi(
        "/api/meter-readings",
        {
          meter_id: meterId,
          reading_date: forms.meterReading.reading_date,
          reading_value: forms.meterReading.reading_value,
        },
        "Zählerstand gespeichert.",
        function () {
          resetForm("meterReading", function (current) {
            return {
              meter_id: current.meter_id,
              reading_date: current.reading_date,
              reading_value: "",
            };
          });
        },
        selectedMeter && selectedMeter.property_id ? String(selectedMeter.property_id) : ""
      );
    }

    function handleExpenseSubmit(event) {
      event.preventDefault();
      const nextPropertyId = resolveExpensePropertyId(
        forms.expense.object_type,
        forms.expense.object_id
      );
      const payload = buildExpensePayload(forms.expense);
      submitToApi(
        "/api/expenses",
        payload,
        "Kosten gespeichert.",
        function () {
          setCreateFormVisible("costs", false);
          resetForm("expense", function (current) {
            return Object.assign({}, createExpenseFormState(), {
              object_type: current.object_type,
              object_id: current.object_id,
              expense_category: "",
              beneficiary_name: "",
              allocation_method: current.allocation_method,
              booking_date: current.booking_date,
              period_start: current.period_start,
              period_end: current.period_end,
              meter_id: "",
              consumption_unit: "",
              consumption_value: "",
              conversion_factor: "",
            });
          });
        },
        nextPropertyId
      );
    }

    function handleExpenseUpdateSubmit(event, expenseId) {
      event.preventDefault();
      const nextPropertyId = resolveExpensePropertyId(
        expenseEditForm.object_type,
        expenseEditForm.object_id
      );
      submitToApi(
        "/api/expenses/" + String(expenseId),
        buildExpensePayload(expenseEditForm),
        "Kosten aktualisiert.",
        function () {
          resetExpenseEdit();
        },
        nextPropertyId,
        "PUT"
      );
    }

    function handlePaperlessSubmit(event) {
      event.preventDefault();
      setSaving(true);
      setError("");
      setStatus("");
      fetchJson("/api/paperless-settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          base_url: paperlessForm.base_url,
          api_token: paperlessForm.api_token,
        }),
      })
        .then(function (payload) {
          setPaperlessSettings(payload);
          setPaperlessForm({
            base_url: payload.base_url || "",
            api_token: "",
          });
          return fetchJson("/api/paperless-status")
            .then(function (statusPayload) {
              setPaperlessStatus(statusPayload);
              setStatus("Paperless-Einstellungen gespeichert.");
            })
            .catch(function () {
              setStatus("Paperless-Einstellungen gespeichert.");
            });
        })
        .catch(function (saveError) {
          setError(saveError.message || "Paperless-Einstellungen konnten nicht gespeichert werden.");
        })
        .finally(function () {
          setSaving(false);
        });
    }

    function handleApplicationSettingsSubmit(event) {
      event.preventDefault();
      setSaving(true);
      setError("");
      setStatus("");
      fetchJson("/api/application-settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          show_delete_actions: !!applicationSettingsForm.show_delete_actions,
        }),
      })
        .then(function (payload) {
          setApplicationSettings(payload);
          setApplicationSettingsForm({
            show_delete_actions: !!payload.show_delete_actions,
          });
          setStatus("Darstellungseinstellungen gespeichert.");
        })
        .catch(function (saveError) {
          setError(saveError.message || "Darstellungseinstellungen konnten nicht gespeichert werden.");
        })
        .finally(function () {
          setSaving(false);
        });
    }

    function buildApplicationExportFilename(exportedAt) {
      const normalizedTimestamp = String(exportedAt || "")
        .replace(/:/g, "-")
        .replace(/\.\d+/g, "")
        .replace(/[^0-9A-Za-z-]/g, "-")
        .replace(/-+/g, "-")
        .replace(/^-|-$/g, "");
      return "easyprent-export-" + (normalizedTimestamp || "backup") + ".json";
    }

    function handleApplicationExport() {
      setSaving(true);
      setError("");
      setStatus("");
      fetchJson("/api/application-export")
        .then(function (payload) {
          const downloadBody = JSON.stringify(payload, null, 2);
          const blob = new Blob([downloadBody], { type: "application/json" });
          const downloadUrl = window.URL.createObjectURL(blob);
          const anchor = document.createElement("a");
          anchor.href = downloadUrl;
          anchor.download = buildApplicationExportFilename(payload.exported_at);
          document.body.appendChild(anchor);
          anchor.click();
          document.body.removeChild(anchor);
          window.setTimeout(function () {
            window.URL.revokeObjectURL(downloadUrl);
          }, 0);
          setStatus("Datenexport erstellt.");
        })
        .catch(function (exportError) {
          setError(exportError.message || "Datenexport konnte nicht erstellt werden.");
        })
        .finally(function () {
          setSaving(false);
        });
    }

    function handleApplicationImportFileChange(fileList) {
      const nextFile = fileList && fileList.length ? fileList[0] : null;
      setApplicationImportFile(nextFile);
      setApplicationImportFileName(nextFile ? nextFile.name : "");
    }

    function handleApplicationImportSubmit(event) {
      event.preventDefault();
      if (!applicationImportFile) {
        setError("Bitte zuerst eine Exportdatei für den Import auswählen.");
        setStatus("");
        return;
      }
      setSaving(true);
      setError("");
      setStatus("");
      Promise.resolve()
        .then(function () {
          return applicationImportFile.text();
        })
        .then(function (rawText) {
          try {
            return JSON.parse(rawText);
          } catch (error) {
            throw new Error("Importdatei enthält kein gültiges JSON.");
          }
        })
        .then(function (payload) {
          return fetchJson("/api/application-import", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
          });
        })
        .then(function () {
          resetApplicationImportSelection();
          return loadDashboard("").then(function () {
            setStatus("Datenimport abgeschlossen.");
          });
        })
        .catch(function (importError) {
          setError(importError.message || "Datenimport konnte nicht durchgeführt werden.");
        })
        .finally(function () {
          setSaving(false);
        });
    }

    if (!overview) {
      return e(
        "div",
        { className: "loading" },
        error ? "Fehler: " + error : "React-Oberfläche wird geladen ..."
      );
    }

    const activeProperties = (overview.properties || []).filter(function (property) {
      return !property.is_archived;
    });
    const activeBuildings = (overview.buildings || []).filter(function (building) {
      return !building.is_archived;
    });
    const activeUnits = (overview.units || []).filter(function (unit) {
      return !unit.is_archived;
    });
    const activeRooms = (overview.rooms || []).filter(function (room) {
      return !room.is_archived;
    });
    const activeTenants = (overview.tenants || []).slice();
    const activeMeters = (overview.meters || []).filter(function (meter) {
      return !meter.is_archived;
    });

    const propertyOptions = activeProperties.map(function (property) {
      return e(
        "option",
        { key: property.id, value: String(property.id) },
        property.name
      );
    });
    const buildingOptions = activeBuildings.map(function (building) {
      return e(
        "option",
        { key: building.id, value: String(building.id) },
        building.name
      );
    });
    const unitOptions = activeUnits.map(function (unit) {
      return e(
        "option",
        { key: unit.id, value: String(unit.id) },
        unit.label
      );
    });
    const leaseRoomOptions = activeRooms
      .filter(function (room) {
        return String(room.unit_id || "") === String(forms.lease.unit_id || "");
      })
      .map(function (room) {
        return e(
          "option",
          { key: room.id, value: String(room.id) },
          room.label
        );
      });
    const roomOptions = activeRooms.map(function (room) {
      return e(
        "option",
        { key: room.id, value: String(room.id) },
        room.label
      );
    });
    const tenantOptions = activeTenants.map(function (tenant) {
      return e(
        "option",
        { key: tenant.id, value: String(tenant.id) },
        tenant.full_name
      );
    });
    function buildMeterOptions(meters) {
      return meters.map(function (meter) {
        return e(
          "option",
          { key: meter.id, value: String(meter.id) },
          meter.label + " (" + meter.unit + ")"
        );
      });
    }
    const meterOptions = buildMeterOptions(activeMeters);
    const expenseMeterOptions = buildMeterOptions(
      activeMeters.filter(function (meter) {
        return (
          String(meter.object_type) === String(forms.expense.object_type) &&
          String(meter.object_id) === String(forms.expense.object_id)
        );
      })
    );
    const expenseEditMeterOptions = buildMeterOptions(
      activeMeters.filter(function (meter) {
        return (
          String(meter.object_type) === String(expenseEditForm.object_type) &&
          String(meter.object_id) === String(expenseEditForm.object_id)
        );
      })
    );
    const expenseTargetGroups = [
      {
        label: "Anlagen",
        object_type: "property",
        items: activeProperties.map(function (property) {
          return { id: property.id, label: property.name };
        }),
      },
      {
        label: "Gebäude",
        object_type: "building",
        items: activeBuildings.map(function (building) {
          return { id: building.id, label: building.name };
        }),
      },
      {
        label: "Wohnungen",
        object_type: "unit",
        items: activeUnits.map(function (unit) {
          return { id: unit.id, label: unit.label };
        }),
      },
      {
        label: "Zimmer",
        object_type: "room",
        items: activeRooms.map(function (room) {
          return { id: room.id, label: room.label };
        }),
      },
    ].filter(function (group) {
      return group.items.length > 0;
    });
    const expenseTargetOptions = expenseTargetGroups.map(function (group) {
      return e(
        "optgroup",
        { key: "expense-target-group-" + group.object_type, label: group.label },
        group.items.map(function (item) {
          return e(
            "option",
            {
              key: group.object_type + "-" + String(item.id),
              value: buildObjectTargetValue(group.object_type, item.id),
            },
            "  " + item.label
          );
        })
      );
    });
    const seenExpenseCategories = {};
    const uniqueExpenseCategories = (overview.expense_categories || []).filter(function (category) {
      const key = String(category.expense_category || "").trim().toLowerCase();
      if (!key || seenExpenseCategories[key]) {
        return false;
      }
      seenExpenseCategories[key] = true;
      return true;
    });
    const expenseCategorySuggestions = uniqueExpenseCategories
      .map(function (category, index) {
        return e("option", {
          key: "expense-category-suggestion-" + String(index),
          value: category.expense_category,
        });
      });
    const expenseCategoryFilterOptions = uniqueExpenseCategories
      .map(function (category, index) {
        return e(
          "option",
          {
            key: "expense-category-filter-" + String(index),
            value: category.expense_category,
          },
          category.expense_category
        );
      });
    const expenseListTargetOptions = expenseTargetGroups.map(function (group) {
      return e(
        "optgroup",
        { key: "expense-list-target-group-" + group.object_type, label: group.label },
        group.items.map(function (item) {
          return e(
            "option",
            {
              key: "expense-list-" + group.object_type + "-" + String(item.id),
              value: buildObjectTargetValue(group.object_type, item.id),
            },
            "  " + item.label
          );
        })
      );
    });
    const showDeleteActions = applicationSettings.show_delete_actions !== false;

    const meterTargetOptions =
      forms.meter.object_type === "building"
        ? buildingOptions
        : forms.meter.object_type === "unit"
          ? unitOptions
          : forms.meter.object_type === "room"
            ? roomOptions
            : propertyOptions;
    const overviewRows = buildOverviewRows({
      overview: overview,
      settlement: settlement,
      depreciation: depreciation,
      selectedMeterId: selectedMeterId,
      onMeterSelect: setActiveMeterSelection,
    });
    const roleItems = overviewRows.roleItems;
    const propertyRows = overviewRows.propertyRows;
    const buildingRows = overviewRows.buildingRows;
    const unitRows = overviewRows.unitRows;
    const roomRows = overviewRows.roomRows;
    const meterRows = overviewRows.meterRows;
    const leaseRows = overviewRows.leaseRows;
    const expenseRows = overviewRows.expenseRows;
    const settlementRows = overviewRows.settlementRows;
    const depreciationRows = overviewRows.depreciationRows;
    const meterData = buildMeterData({
      overview: overview,
      selectedMeterId: selectedMeterId,
      onDeleteMeterReading: deleteMeterReading,
      saving: saving,
      loading: loading,
      showDeleteActions: showDeleteActions,
    });
    const selectedMeter = meterData.selectedMeter;
    const selectedMeterReadings = meterData.selectedMeterReadings;
    const meterReadingRows = meterData.meterReadingRows;
    const meterChartSeries = buildMeterChartSeries(
      selectedMeterReadings,
      meterChartGranularity,
      meterChartMode,
      meterInterpolationMode,
      meterChartRange.from,
      meterChartRange.to
    );
    const meterConsumptionSummary = buildMeterConsumptionSummary(
      selectedMeterReadings,
      meterChartGranularity,
      meterInterpolationMode,
      meterChartRange.from,
      meterChartRange.to
    );
    const actualMeterReadings = buildActualMeterReadings(
      selectedMeterReadings,
      meterChartRange.from,
      meterChartRange.to
    );
    const expenseListFilteredExpenses = buildFilteredExpenses(
      overview.expenses || [],
      expenseListFilters
    );
    const filteredExpenses = buildFilteredExpenses(
      overview.expenses || [],
      Object.assign({}, expenseListFilters, { year: "" })
    );
    const expenseCategoryPeriodTotals = buildExpenseCategoryPeriodTotals(
      filteredExpenses,
      overview.meter_readings || [],
      expenseChartConfig.from,
      expenseChartConfig.to
    );
    const expenseDevelopmentExpenses = filteredExpenses.filter(function (expense) {
      return expenseChartConfig.include_archived || !expense.is_archived;
    });
    const expenseDevelopmentSeries = buildExpenseDevelopmentSeries(
      expenseDevelopmentExpenses,
      overview.meter_readings || [],
      expenseChartConfig.granularity,
      expenseChartConfig.from,
      expenseChartConfig.to
    );
    const expenseDevelopmentCompositionSeries = buildExpenseDevelopmentCompositionSeries(
      expenseDevelopmentExpenses,
      overview.meter_readings || [],
      expenseChartConfig.granularity,
      expenseChartConfig.from,
      expenseChartConfig.to
    );
    const expenseDevelopmentMonthlySeries = buildExpenseDevelopmentSeries(
      expenseDevelopmentExpenses,
      overview.meter_readings || [],
      "months",
      expenseChartConfig.from,
      expenseChartConfig.to
    );
    const expenseDevelopmentTotal = expenseDevelopmentMonthlySeries.reduce(function (total, item) {
      return total + Number(item.value || 0);
    }, 0);

    function tabButton(tabKey, label) {
      return e(
        "button",
        {
          type: "button",
          className: "tab" + (activeTab === tabKey ? " active" : ""),
          onClick: function () {
            setActiveTab(tabKey);
          },
        },
        label
      );
    }

    function mainTabButton(tabKey, label) {
      return e(
        "button",
        {
          type: "button",
          className: "tab" + (mainTab === tabKey ? " active" : ""),
          onClick: function () {
            setMainTab(tabKey);
            if (
              tabKey === "objects" &&
              ["properties", "buildings", "units", "rooms"].indexOf(activeTab) === -1
            ) {
              setActiveTab("properties");
            }
            if (
              tabKey === "cost_management" &&
              ["meters", "costs"].indexOf(activeTab) === -1
            ) {
              setActiveTab("costs");
            }
            if (
              tabKey === "tenant_management" &&
              ["tenants", "leases"].indexOf(activeTab) === -1
            ) {
              setActiveTab("tenants");
            }
          },
        },
        label
      );
    }

    const isActiveEntityEditing =
      Object.prototype.hasOwnProperty.call(editingEntityIds, activeTab) &&
      String(editingEntityIds[activeTab] || "") !== "";

    const activeFormDescriptor = renderManagementActiveForm({
      activeTab: activeTab,
      editingEntityIds: editingEntityIds,
      forms: forms,
      saving: saving,
      loading: loading,
      handlePropertySubmit: handlePropertySubmit,
      handleBuildingSubmit: handleBuildingSubmit,
      handleUnitSubmit: handleUnitSubmit,
      handleRoomSubmit: handleRoomSubmit,
      handleTenantSubmit: handleTenantSubmit,
      handleLeaseSubmit: handleLeaseSubmit,
      handleMeterSubmit: handleMeterSubmit,
      handleMeterReadingSubmit: handleMeterReadingSubmit,
      handleExpenseSubmit: handleExpenseSubmit,
      setFormField: setFormField,
      setUnitBuildingId: setUnitBuildingId,
      setLeaseUnitId: setLeaseUnitId,
      setLeaseRoomId: setLeaseRoomId,
      clearEditingForTab: clearEditingForTab,
      cancelManagementEdit: cancelManagementEdit,
      onTenantDelete: handleTenantDelete,
      onLeaseDelete: handleLeaseDelete,
      showDeleteActions: showDeleteActions,
      propertyOptions: propertyOptions,
      buildingOptions: buildingOptions,
      unitOptions: unitOptions,
      leaseRoomOptions: leaseRoomOptions,
      tenantOptions: tenantOptions,
      meterOptions: meterOptions,
      expenseMeterOptions: expenseMeterOptions,
      meterTargetOptions: meterTargetOptions,
      expenseTargetOptions: expenseTargetOptions,
      expenseCategorySuggestions: expenseCategorySuggestions,
      managementDocuments: managementDocuments,
      managementUploadFiles: managementUploadFiles,
      managementDocumentReferenceId: managementDocumentReferenceId,
      managementUploadInputKey: managementUploadInputKey,
      onManagementDocumentSelection: handleManagementDocumentSelection,
      onManagementDocumentReferenceIdChange: setManagementDocumentReferenceId,
      onManagementDocumentReferenceCreate: handleManagementDocumentReferenceCreate,
      onManagementDocumentUpload: handleManagementDocumentUpload,
      onManagementDocumentDelete: handleManagementDocumentDelete,
      overview: overview,
      calculateMeterConsumptionValue: calculateMeterConsumptionValue,
      setExpenseCategoryValue: setExpenseCategoryValue,
      setExpenseTargetValue: setExpenseTargetValue,
      setExpenseMeterId: setExpenseMeterId,
      setMeterObjectType: setMeterObjectType,
      setActiveMeterSelection: setActiveMeterSelection,
    });
    const activeHeading = activeFormDescriptor.activeHeading;
    const activeForm = activeFormDescriptor.activeForm;

    const managementPreview = buildManagementPreview({
      activeTab: activeTab,
      overview: overview,
      managementListFilters: managementListFilters,
      onManagementFilterChange: setManagementListFilter,
      editingEntityIds: editingEntityIds,
      selectedMeterId: selectedMeterId,
      onPropertyEdit: startPropertyEdit,
      onBuildingEdit: startBuildingEdit,
      onUnitEdit: startUnitEdit,
      onRoomEdit: startRoomEdit,
      onTenantEdit: startTenantEdit,
      onLeaseEdit: startLeaseEdit,
      onMeterSelect: setActiveMeterSelection,
      onMeterEdit: startMeterEdit,
      meterActionCell: function (meter) {
        return objectActionCell("meters", meter, startMeterEdit);
      },
      objectActionCell: objectActionCell,
      expenseListFilters: expenseListFilters,
      onExpenseListFilterChange: function (field, value) {
        setExpenseListFilters(function (current) {
          return Object.assign({}, current, {
            [field]: value,
          });
        });
      },
      expenseListTargetOptions: expenseListTargetOptions,
      expenseCategoryFilterOptions: expenseCategoryFilterOptions,
      filteredExpenses: expenseListFilteredExpenses,
      editingExpenseId: editingExpenseId,
      onExpenseEdit: startExpenseEdit,
      expenseEditForm: expenseEditForm,
      onExpenseUpdateSubmit: handleExpenseUpdateSubmit,
      onExpenseEditFieldChange: setExpenseEditField,
      onExpenseEditCategoryChange: setExpenseEditCategoryValue,
      onExpenseEditTargetChange: setExpenseEditTargetValue,
      onExpenseEditMeterChange: setExpenseEditMeterId,
      onExpenseArchive: function (expense) {
        performObjectAction(
          "/api/expenses/" + String(expense.id) + "/archive",
          "POST",
          formatDisplayName(expense) + " archiviert.",
          ""
        );
        resetExpenseEdit();
      },
      onExpenseEditCancel: resetExpenseEdit,
      expenseTargetOptions: expenseTargetOptions,
      expenseCategorySuggestions: expenseCategorySuggestions,
      meterOptions: meterOptions,
      expenseEditMeterOptions: expenseEditMeterOptions,
      calculateMeterConsumptionValue: calculateMeterConsumptionValue,
      saving: saving,
      loading: loading,
      expenseDocuments: expenseDocuments,
      expenseUploadFiles: expenseUploadFiles,
      expenseDocumentReferenceId: expenseDocumentReferenceId,
      expenseUploadInputKey: expenseUploadInputKey,
      onExpenseDocumentSelection: handleExpenseDocumentSelection,
      onExpenseDocumentReferenceIdChange: setExpenseDocumentReferenceId,
      onExpenseDocumentReferenceCreate: handleExpenseDocumentReferenceCreate,
      onExpenseDocumentUpload: handleExpenseDocumentUpload,
      onExpenseDocumentDelete: handleExpenseDocumentDelete,
      showDeleteActions: showDeleteActions,
      activeInlineEditorHeading:
        ["properties", "buildings", "units", "rooms", "tenants", "leases", "meters"].indexOf(activeTab) >= 0 &&
        isActiveEntityEditing
          ? activeHeading
          : "",
      activeInlineEditorForm:
        ["properties", "buildings", "units", "rooms", "tenants", "leases", "meters"].indexOf(activeTab) >= 0 &&
        isActiveEntityEditing
          ? activeForm
          : null,
    });
    const previewTitle = managementPreview.previewTitle;
    const previewDescription = managementPreview.previewDescription;
    const previewToolbar = managementPreview.previewToolbar;
    const previewHeaders = managementPreview.previewHeaders;
    const previewRows = managementPreview.previewRows;

    const isCostManagementMainTab = mainTab === "cost_management";
    const isTenantManagementMainTab = mainTab === "tenant_management";
    const isPreviewCollapsible = activeTab === "costs";
    const isPreviewExpanded = !isPreviewCollapsible || previewVisibility.costs !== false;
    const createActionLabel = isCostManagementMainTab
      ? activeTab === "meters"
        ? "Zähler erzeugen"
        : "Kostenposten erzeugen"
      : isTenantManagementMainTab
        ? activeTab === "leases"
          ? "Mietvertrag erzeugen"
          : "Mieter erzeugen"
        : "Objekt erzeugen";
    const isCreateFormExpanded = !!createFormVisibility[activeTab];
    const shouldShowActiveForm = isCreateFormExpanded;

    const mainTabButtons = [
      mainTabButton("overview", "Übersicht"),
      mainTabButton("objects", "Objektverwaltung"),
      mainTabButton("cost_management", "Kostenverwaltung"),
      mainTabButton("tenant_management", "Mieterverwaltung"),
      mainTabButton("settings", "Einstellungen"),
    ];
    const managementTabButtons = [
      isCostManagementMainTab
        ? tabButton("meters", "Zähler")
        : isTenantManagementMainTab
          ? tabButton("tenants", "Mieter")
          : tabButton("properties", "Anlagen"),
      isCostManagementMainTab
        ? tabButton("costs", "Kosten")
        : isTenantManagementMainTab
          ? tabButton("leases", "Mietverträge")
          : tabButton("buildings", "Gebäude"),
      isCostManagementMainTab || isTenantManagementMainTab
        ? null
        : tabButton("units", "Wohnungen"),
      isCostManagementMainTab || isTenantManagementMainTab
        ? null
        : tabButton("rooms", "Zimmer"),
    ].filter(Boolean);
    const managementHint = isCostManagementMainTab
      ? activeTab === "meters"
        ? "Zähler werden einem Objekt zugeordnet. Im selben Tab können neue Zählerstände mit Datum und Wert erfasst werden."
        : "Kosten werden über ein gemeinsames, gruppiertes Zielobjekt-Feld zugeordnet. Beim Tippen im Feld Kostenart werden vorhandene Kostenarten vorgeschlagen. Gesamtkosten und wiederholende Kosten werden über einen Zeitraum erfasst, verbrauchsbezogene Kosten nutzen entweder einen manuellen Verbrauchswert oder einen Zähler mit optionalem Umrechnungsfaktor. Bestehende Kosten bearbeitest du per Klick auf die jeweilige Zeile."
      : isTenantManagementMainTab
        ? activeTab === "tenants"
          ? "Lege neue Mieter mit Kontaktdaten an. Filtere die Liste und klicke auf einen Eintrag, um ihn zu bearbeiten."
          : "Erfasse Mietverträge über Mieter- sowie Wohnungs- oder Zimmerzuordnung mit Konditionen und Laufzeit. Filtere die Liste und klicke auf einen Eintrag, um ihn zu bearbeiten."
        : activeTab === "properties"
          ? "Lege eine neue Anlage an. Die Objektliste zeigt immer alle Anlagen, Gebäude, Wohnungen und Zimmer in ihrer Eltern-Kind-Struktur. Filtere die Liste und klicke auf einen Eintrag, um ihn zu bearbeiten."
          : activeTab === "buildings"
            ? "Gebäude können einer Anlage zugeordnet oder standalone angelegt werden. Die Objektliste zeigt alle Objekte hierarchisch mit Eltern- und Kindbezug. Filtere die Liste und klicke auf einen Eintrag, um ihn zu bearbeiten."
            : activeTab === "units"
              ? "Wohnungen können einem Gebäude zugeordnet oder standalone angelegt werden und brauchen eigene Adressen. Die Objektliste zeigt alle Objekte hierarchisch mit Eltern- und Kindbezug. Filtere die Liste und klicke auf einen Eintrag, um ihn zu bearbeiten."
              : "Zimmer müssen immer einer Wohnung zugeordnet sein und dürfen die hinterlegte Zimmeranzahl der Wohnung nicht überschreiten. Die Objektliste zeigt alle Objekte hierarchisch mit Eltern- und Kindbezug. Filtere die Liste und klicke auf einen Eintrag, um ihn zu bearbeiten.";
    const supplementalContent =
      mainTab === "cost_management" && activeTab === "meters"
        ? e(MeterSupplementalPanels, {
            selectedMeter: selectedMeter,
            meterReadingRows: meterReadingRows,
            meterChartRange: meterChartRange,
            onMeterChartRangeBoundaryChange: setMeterChartRangeBoundary,
            meterChartGranularity: meterChartGranularity,
            onMeterChartGranularityChange: setMeterChartGranularity,
            meterChartMode: meterChartMode,
            onMeterChartModeChange: setMeterChartMode,
            meterInterpolationMode: meterInterpolationMode,
            onMeterInterpolationModeChange: setMeterInterpolationMode,
            meterChartSeries: meterChartSeries,
            actualMeterReadings: actualMeterReadings,
            meterConsumptionSummary: meterConsumptionSummary,
          })
        : mainTab === "cost_management" && activeTab === "costs"
          ? e(ExpenseDevelopmentPanel, {
              expenseChartConfig: expenseChartConfig,
              onExpenseChartRangeBoundaryChange: setExpenseChartRangeBoundary,
              onExpenseChartConfigChange: function (changes) {
                setExpenseChartConfig(function (current) {
                  return Object.assign({}, current, changes);
                });
              },
              expenseDevelopmentSeries: expenseDevelopmentSeries,
              expenseDevelopmentCompositionSeries: expenseDevelopmentCompositionSeries,
              expenseDevelopmentMonthlySeries: expenseDevelopmentMonthlySeries,
              expenseDevelopmentTotal: Number(expenseDevelopmentTotal.toFixed(2)),
              expenseCategoryPeriodTotals: expenseCategoryPeriodTotals,
              expenseCategoryPeriod: {
                from: expenseChartConfig.from,
                to: expenseChartConfig.to,
              },
              onExpenseCategoryPeriodChange: setExpenseChartRangeBoundary,
            })
          : null;

    const mainContent =
      mainTab === "overview"
        ? e(OverviewContent, {
            summary: overview.summary,
            roleItems: roleItems,
            propertyRows: propertyRows,
            buildingRows: buildingRows,
            unitRows: unitRows,
            roomRows: roomRows,
            meterRows: meterRows,
            leaseRows: leaseRows,
            settlementRows: settlementRows,
            expenseRows: expenseRows,
            depreciationRows: depreciationRows,
            settlement: settlement,
            properties: overview.properties,
            units: overview.units,
            settlementFilters: settlementFilters,
            onSettlementFilterChange: handleSettlementFilterChange,
            onSettlementFilterSubmit: handleSettlementFilterSubmit,
            depreciation: depreciation,
            depreciationYear: bootstrap.depreciationYear,
          })
        : mainTab === "settings"
          ? e(SettingsContent, {
              onPaperlessSubmit: handlePaperlessSubmit,
              onApplicationSettingsSubmit: handleApplicationSettingsSubmit,
              paperlessForm: paperlessForm,
              onFieldChange: setPaperlessField,
              paperlessSettings: paperlessSettings,
              applicationSettings: applicationSettings,
              applicationSettingsForm: applicationSettingsForm,
              onApplicationSettingsFieldChange: setApplicationSettingsField,
              onApplicationExport: handleApplicationExport,
              onApplicationImportSubmit: handleApplicationImportSubmit,
              onApplicationImportFileChange: handleApplicationImportFileChange,
              applicationImportFileName: applicationImportFileName,
              applicationImportInputKey: applicationImportInputKey,
              serverStatus: serverStatus,
              paperlessStatus: paperlessStatus,
              isActionDisabled: saving || loading,
              saving: saving,
            })
          : e(ManagementContent, {
              createActionLabel: createActionLabel,
              managementTabButtons: managementTabButtons,
              managementHint: managementHint,
              shouldShowActiveForm: shouldShowActiveForm,
              activeHeading: activeHeading,
              activeForm: activeForm,
              previewTitle: previewTitle,
              previewDescription: previewDescription,
              previewToolbar: previewToolbar,
              previewHeaders: previewHeaders,
              previewRows: previewRows,
              isPreviewCollapsible: isPreviewCollapsible,
              isPreviewExpanded: isPreviewExpanded,
              isActionDisabled: saving || loading,
              onToggleCreateForm: function () {
                if (shouldShowActiveForm) {
                  setCreateFormVisible(activeTab, false);
                  return;
                }
                openCreateForm(activeTab);
              },
              onTogglePreview: function () {
                if (!isPreviewCollapsible) {
                  return;
                }
                setPreviewVisibility(function (current) {
                  return Object.assign({}, current, {
                    costs: !isPreviewExpanded,
                  });
                });
              },
              supplementalContent: supplementalContent,
            });

    return e(AppShell, {
      openApiUrl: bootstrap.openApiUrl,
      mainTabButtons: mainTabButtons,
      error: error,
      status: status,
      mainContent: mainContent,
    });
  }

  ReactDOM.createRoot(rootNode).render(e(App));
})();
