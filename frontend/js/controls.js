/* ==========================================================================
 * controls.js —— 交互式参数控件（FR-07 / FR-08）
 * 与后端 backend/parsers/param_parser.py 的 @param 语法保持一致。
 *
 *   # @param n 样本量 slider min=1 max=100 step=1 default=10
 *   # @param algo 算法 select options=快速,归并 default=快速
 * ========================================================================== */
window.App = window.App || {};

(function () {
  const PARAM_RE =
    /^\s*(?:#|\/\/)\s*@param\s+(\w+)\s+(?:"([^"]*)"|(\S*))\s*(\w+)?\s*((?:\w+=\S*\s*)*)$/;
  const KV_RE = /(\w+)=(\S+)/g;

  /** 从代码中解析控件定义 */
  App.parseParams = function (code) {
    const params = [];
    for (const line of code.split(/\r?\n/)) {
      const m = PARAM_RE.exec(line);
      if (!m) continue;
      const [, name, labelQ, labelP, kindRaw, optsRaw] = m;
      const kind = ["slider", "number", "select", "text", "checkbox"].includes(
        (kindRaw || "").toLowerCase()
      )
        ? kindRaw.toLowerCase()
        : "number";
      const kv = {};
      let kvMatch;
      KV_RE.lastIndex = 0;
      while ((kvMatch = KV_RE.exec(optsRaw || ""))) kv[kvMatch[1]] = kvMatch[2];
      params.push({
        name,
        label: labelQ || labelP || name,
        kind,
        min: kv.min !== undefined ? parseFloat(kv.min) : null,
        max: kv.max !== undefined ? parseFloat(kv.max) : null,
        step: kv.step !== undefined ? parseFloat(kv.step) : null,
        options: kv.options ? kv.options.split(",") : [],
        default: kv.default,
      });
    }
    return params;
  };

  /** 判断代码中是否含 @param 声明 */
  App.hasParams = function (code) {
    return App.parseParams(code).length > 0;
  };

  /**
   * 在容器中渲染控件；参数变化触发 onChange(values)（用于 FR-08 联动执行）。
   * @returns {Function} collect() —— 获取当前参数值集合
   */
  App.renderControls = function (container, params, onChange) {
    container.innerHTML = "";
    const values = {};

    for (const p of params) {
      const init = defaultValue(p);
      values[p.name] = init;

      const wrap = document.createElement("span");
      wrap.className = "nb-param";
      const label = document.createElement("label");
      label.textContent = p.label;
      wrap.appendChild(label);
      wrap.appendChild(buildInput(p, init, values, onChange));
      container.appendChild(wrap);
    }

    return () => values;
  };

  /** 构建单个控件（含数值徽标等附加元素） */
  function buildInput(p, init, values, onChange) {
    const box = document.createElement("span");
    box.style.display = "inline-flex";
    box.style.alignItems = "center";
    box.style.gap = "4px";

    const input = document.createElement("input");

    switch (p.kind) {
      case "slider": {
        input.type = "range";
        input.min = p.min ?? 0;
        input.max = p.max ?? 100;
        input.step = p.step ?? 1;
        input.value = init;
        const badge = document.createElement("span");
        badge.className = "nb-value";
        badge.textContent = String(init);
        input.addEventListener("input", () => {
          badge.textContent = input.value;
          values[p.name] = parseFloat(input.value);
          onChange(values);
        });
        box.appendChild(input);
        box.appendChild(badge);
        return box;
      }
      case "select": {
        const sel = document.createElement("select");
        for (const opt of p.options) {
          const o = document.createElement("option");
          o.value = o.textContent = opt;
          sel.appendChild(o);
        }
        sel.value = init;
        sel.addEventListener("change", () => {
          values[p.name] = sel.value;
          onChange(values);
        });
        return sel;
      }
      case "checkbox": {
        input.type = "checkbox";
        input.checked = !!init;
        input.addEventListener("change", () => {
          values[p.name] = input.checked;
          onChange(values);
        });
        return input;
      }
      default: {
        // number / text
        input.type = p.kind === "number" ? "number" : "text";
        if (p.min !== null) input.min = p.min;
        if (p.max !== null) input.max = p.max;
        if (p.step !== null) input.step = p.step;
        input.value = init;
        input.addEventListener("change", () => {
          values[p.name] =
            p.kind === "number" ? parseFloat(input.value) : input.value;
          onChange(values);
        });
        return input;
      }
    }
  }

  function defaultValue(p) {
    if (p.kind === "slider" || p.kind === "number")
      return p.default !== undefined ? parseFloat(p.default) : (p.min ?? 0);
    if (p.kind === "select") return p.default ?? p.options[0];
    if (p.kind === "checkbox")
      return ["1", "true", "yes", "on"].includes(String(p.default).toLowerCase());
    return p.default ?? "";
  }

  /** 生成实际执行的代码：删 @param 行 + 头部注入赋值（与后端逻辑一致） */
  App.buildExecutableCode = function (language, code, values) {
    const comment = language === "javascript" ? "//" : "#";
    const pure = code
      .split(/\r?\n/)
      .filter((ln) => !PARAM_RE.test(ln))
      .join("\n");
    const head = [`${comment} ---- 交互参数（自动生成） ----`];
    for (const [k, v] of Object.entries(values || {})) {
      if (!/^\w+$/.test(k)) continue;
      head.push(`${k} = ${literal(language, v)}`);
    }
    return head.join("\n") + "\n\n" + pure;
  };

  function literal(language, v) {
    if (typeof v === "number" || typeof v === "boolean") return String(v);
    const s = String(v).replace(/\\/g, "\\\\").replace(/'/g, "\\'");
    return `'${s}'`;
  }
})();
