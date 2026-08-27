(function () {
  if (!window.React) {
    return;
  }

  const domain = window.EasyPrentAppDomain || {};
  const e = React.createElement;
  const useEffect = React.useEffect;
  const useRef = React.useRef;
  const formatNumericLabel =
    domain.formatNumericLabel ||
    function (value) {
      if (value == null || Number.isNaN(value)) {
        return "-";
      }
      const rounded = Math.round(value * 100) / 100;
      return Number.isInteger(rounded) ? String(rounded) : String(rounded.toFixed(2));
    };

  function ExpenseDevelopmentChart(props) {
    const chartHostRef = useRef(null);
    const chartInstanceRef = useRef(null);
    const series = props.series || [];
    const compositionSeries = props.compositionSeries || [];
    const chartMode = props.chartMode || "bars";
    const hasCompositionBars = chartMode === "bars" && compositionSeries.length > 0;
    const hasValues = series.some(function (item) {
      return item.value != null;
    });

    useEffect(
      function () {
        if (!window.echarts || !chartHostRef.current || !hasValues) {
          return;
        }
        if (!chartInstanceRef.current) {
          chartInstanceRef.current = window.echarts.init(chartHostRef.current);
        }
        const chart = chartInstanceRef.current;

        chart.setOption(
          {
            animation: true,
            tooltip: {
              trigger: "axis",
              axisPointer: {
                type: chartMode === "bars" ? "shadow" : "line",
              },
              formatter: function (params) {
                const periodLabel =
                  params && params[0] ? String(params[0].axisValueLabel || params[0].axisValue || "") : "";
                if (hasCompositionBars) {
                  const tooltipLines = ["<strong>" + periodLabel + "</strong>"];
                  let totalValue = 0;
                  (params || []).forEach(function (entry) {
                    const value = Number(Array.isArray(entry.value) ? entry.value[1] : entry.value);
                    if (Number.isNaN(value)) {
                      return;
                    }
                    totalValue += value;
                    if (value === 0) {
                      return;
                    }
                    tooltipLines.push(
                      entry.marker +
                        " " +
                        entry.seriesName +
                        ": " +
                        formatNumericLabel(value) +
                        " EUR"
                    );
                  });
                  tooltipLines.push("Gesamt: " + formatNumericLabel(totalValue) + " EUR");
                  return tooltipLines.join("<br/>");
                }
                const value =
                  params && params[0]
                    ? Number(Array.isArray(params[0].value) ? params[0].value[1] : params[0].value)
                    : null;
                return [
                  "<strong>" + periodLabel + "</strong>",
                  "Kosten: " + formatNumericLabel(value) + " EUR",
                ].join("<br/>");
              },
            },
            legend: hasCompositionBars
              ? {
                  top: 0,
                  left: "center",
                  type: "scroll",
                  textStyle: { color: "#52606d" },
                }
              : undefined,
            grid: {
              left: 48,
              right: 20,
              top: hasCompositionBars ? 62 : 24,
              bottom: 52,
              containLabel: true,
            },
            color: [
              "rgba(15, 118, 110, 0.92)",
              "rgba(180, 83, 9, 0.9)",
              "rgba(30, 64, 175, 0.9)",
              "rgba(190, 24, 93, 0.9)",
              "rgba(67, 56, 202, 0.9)",
              "rgba(5, 150, 105, 0.9)",
              "rgba(192, 38, 211, 0.9)",
              "rgba(124, 58, 237, 0.9)",
            ],
            xAxis: {
              type: "category",
              data: series.map(function (item) {
                return item.label;
              }),
              axisLabel: { color: "#52606d" },
              axisLine: { lineStyle: { color: "rgba(31, 41, 51, 0.2)" } },
            },
            yAxis: {
              type: "value",
              scale: true,
              min: "dataMin",
              max: "dataMax",
              axisLabel: {
                color: "#52606d",
                formatter: function (value) {
                  return formatNumericLabel(Number(value));
                },
              },
              splitLine: { lineStyle: { color: "rgba(31, 41, 51, 0.12)" } },
            },
            series: hasCompositionBars
              ? compositionSeries.map(function (segment) {
                  return {
                    name: segment.name,
                    type: "bar",
                    stack: "expense-composition",
                    data: segment.data,
                    emphasis: {
                      focus: "series",
                    },
                    barMaxWidth: 28,
                  };
                })
              : [
                  {
                    name: "Kostenentwicklung",
                    type: chartMode === "line" ? "line" : "bar",
                    data: series.map(function (item) {
                      return item.value;
                    }),
                    smooth: chartMode === "line" ? 0.22 : false,
                    lineStyle: {
                      color: "rgba(15, 118, 110, 0.9)",
                      width: 3,
                    },
                    itemStyle: {
                      color: "rgba(180, 83, 9, 0.84)",
                    },
                    barMaxWidth: 28,
                  },
                ],
          },
          true
        );
        chart.resize();

        const handleResize = function () {
          if (chartInstanceRef.current) {
            chartInstanceRef.current.resize();
          }
        };
        window.addEventListener("resize", handleResize);
        return function () {
          window.removeEventListener("resize", handleResize);
        };
      },
      [series, compositionSeries, chartMode, hasCompositionBars, hasValues]
    );

    useEffect(function () {
      return function () {
        if (chartInstanceRef.current) {
          chartInstanceRef.current.dispose();
          chartInstanceRef.current = null;
        }
      };
    }, []);

    if (!window.echarts) {
      return e("p", { className: "hint" }, "Diagramm-Bibliothek nicht verfügbar. Bitte Seite neu laden.");
    }
    if (!hasValues) {
      return e("p", { className: "hint" }, "Für die gewählte Konfiguration sind keine Kostendaten vorhanden.");
    }

    return e(
      "div",
      { className: "chart-card" },
      e("div", { className: "echarts-host", ref: chartHostRef })
    );
  }

  function MeterChart(props) {
    const chartHostRef = useRef(null);
    const chartInstanceRef = useRef(null);
    const series = props.series || [];
    const actualReadings = props.actualReadings || [];
    const chartMode = props.chartMode || "cumulative";
    const hasValues = series.some(function (item) {
      return item.value != null;
    });

    useEffect(
      function () {
        if (!window.echarts || !chartHostRef.current || !hasValues) {
          return;
        }

        if (!chartInstanceRef.current) {
          chartInstanceRef.current = window.echarts.init(chartHostRef.current);
        }
        const chart = chartInstanceRef.current;
        const optionSeriesData = series.map(function (item) {
          if (chartMode === "bars") {
            return {
              value: item.value == null ? null : Number(item.value),
              source_type: item.source_type || "interpolated",
            };
          }
          return {
            value: item.value == null ? null : [item.timestamp, Number(item.value)],
            source_type: item.source_type || "interpolated",
          };
        });
        const actualSeriesData = actualReadings.map(function (item) {
          return {
            value: [item.timestamp, Number(item.value)],
            source_type: "recorded",
            reading_date: item.label,
          };
        });
        const useCategoryXAxis = chartMode === "bars";
        const xAxis = useCategoryXAxis
          ? {
              type: "category",
              data: series.map(function (item) {
                return item.label;
              }),
              axisLabel: { color: "#52606d" },
              axisLine: { lineStyle: { color: "rgba(31, 41, 51, 0.2)" } },
            }
          : {
              type: "time",
              axisLabel: { color: "#52606d" },
              axisLine: { lineStyle: { color: "rgba(31, 41, 51, 0.2)" } },
            };
        const primarySeries = {
          name: chartMode === "bars" ? "Verbrauch je Zeitraum" : "Periodenwert",
          type: chartMode === "bars" ? "bar" : "line",
          data: optionSeriesData,
          smooth: chartMode === "bars" ? false : 0.24,
          showSymbol: chartMode !== "bars",
          symbolSize: function (value, params) {
            return params.data && params.data.source_type === "recorded" ? 9 : 8;
          },
          symbol: function (value, params) {
            return params.data && params.data.source_type === "recorded" ? "circle" : "rect";
          },
          lineStyle: {
            color: "rgba(15, 118, 110, 0.9)",
            width: 3,
          },
          itemStyle: {
            color: function (params) {
              return params.data && params.data.source_type === "recorded"
                ? "rgba(15, 118, 110, 0.9)"
                : "rgba(180, 83, 9, 0.86)";
            },
          },
          barMaxWidth: 28,
        };
        const chartSeries = [primarySeries];
        if (!useCategoryXAxis && actualSeriesData.length) {
          chartSeries.push({
            name: "Tatsächlicher Zählerstand",
            type: "scatter",
            data: actualSeriesData,
            symbol: "circle",
            symbolSize: 9,
            itemStyle: {
              color: "rgba(15, 118, 110, 0.92)",
              borderColor: "#ffffff",
              borderWidth: 1.5,
            },
            z: 4,
          });
        }

        chart.setOption(
          {
            animation: true,
            tooltip: {
              trigger: "axis",
              axisPointer: {
                type: chartMode === "bars" ? "shadow" : "cross",
              },
              formatter: function (params) {
                const periodLabel =
                  params && params[0] ? String(params[0].axisValueLabel || params[0].axisValue || "") : "";
                const tooltipLines = ["<strong>" + periodLabel + "</strong>"];
                (params || []).forEach(function (entry) {
                  const point = entry.data || {};
                  const rawValue = Array.isArray(point.value) ? point.value[1] : point.value;
                  const sourceLabel =
                    point.source_type === "recorded"
                      ? "Messpunkt"
                      : "Interpolierter Periodenpunkt";
                  tooltipLines.push(
                    entry.marker +
                      " " +
                      entry.seriesName +
                      ": " +
                      formatNumericLabel(rawValue) +
                      (point.source_type ? " | " + sourceLabel : "")
                  );
                });
                return tooltipLines.join("<br/>");
              },
            },
            grid: {
              left: 48,
              right: 20,
              top: 24,
              bottom: 52,
              containLabel: true,
            },
            xAxis: xAxis,
            yAxis: {
              type: "value",
              scale: true,
              min: "dataMin",
              max: "dataMax",
              axisLabel: {
                color: "#52606d",
                formatter: function (value) {
                  return formatNumericLabel(Number(value));
                },
              },
              splitLine: { lineStyle: { color: "rgba(31, 41, 51, 0.12)" } },
            },
            series: chartSeries,
          },
          true
        );
        chart.resize();

        const handleResize = function () {
          if (chartInstanceRef.current) {
            chartInstanceRef.current.resize();
          }
        };
        window.addEventListener("resize", handleResize);
        return function () {
          window.removeEventListener("resize", handleResize);
        };
      },
      [series, actualReadings, chartMode, hasValues]
    );

    useEffect(function () {
      return function () {
        if (chartInstanceRef.current) {
          chartInstanceRef.current.dispose();
          chartInstanceRef.current = null;
        }
      };
    }, []);

    if (!window.echarts) {
      return e(
        "p",
        { className: "hint" },
        "Diagramm-Bibliothek nicht verfügbar. Bitte Seite neu laden."
      );
    }

    if (!hasValues) {
      return e("p", { className: "hint" }, "Für die ausgewählte Ansicht sind noch keine Diagrammdaten vorhanden.");
    }

    return e(
      "div",
      { className: "chart-card" },
      e("div", { className: "echarts-host", ref: chartHostRef }),
      e(
        "div",
        { className: "chart-labels" },
        e("span", { className: "point-source-recorded" }, "Messpunkt"),
        e("span", { className: "point-source-interpolated" }, "Interpolierter Periodenpunkt")
      )
    );
  }

  window.EasyPrentAppCharts = {
    ExpenseDevelopmentChart: ExpenseDevelopmentChart,
    MeterChart: MeterChart,
  };
})();
