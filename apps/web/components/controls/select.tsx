"use client";

import { Check, ChevronDown } from "lucide-react";
import { type KeyboardEvent, type ReactNode, useEffect, useId, useRef, useState } from "react";

export type ControlOption = {
  readonly value: string;
  readonly label: string;
};

const TYPEAHEAD_RESET_MS = 600;

/**
 * Shared popover listbox state: open/close, roving active index, outside-click
 * dismissal, and the keyboard contract (Arrow/Home/End/Enter/Esc/Tab + type-ahead).
 * The trigger button keeps DOM focus and drives the list via aria-activedescendant.
 */
function useListbox(options: readonly ControlOption[], onPick: (value: string) => void) {
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const rootRef = useRef<HTMLDivElement | null>(null);
  const typeahead = useRef({ query: "", at: 0 });

  useEffect(() => {
    if (!open) {
      return;
    }
    const onDocMouseDown = (event: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onDocMouseDown);
    return () => document.removeEventListener("mousedown", onDocMouseDown);
  }, [open]);

  const handleKeyDown = (event: KeyboardEvent, closeOnPick: boolean) => {
    if (!open) {
      if (event.key === "ArrowDown" || event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        setOpen(true);
      }
      return;
    }
    const count = options.length;
    switch (event.key) {
      case "ArrowDown":
        event.preventDefault();
        setActive((index) => (count === 0 ? 0 : (index + 1) % count));
        break;
      case "ArrowUp":
        event.preventDefault();
        setActive((index) => (count === 0 ? 0 : (index - 1 + count) % count));
        break;
      case "Home":
        event.preventDefault();
        setActive(0);
        break;
      case "End":
        event.preventDefault();
        setActive(Math.max(0, count - 1));
        break;
      case "Enter":
      case " ": {
        event.preventDefault();
        const option = options[active];
        if (option) {
          onPick(option.value);
          if (closeOnPick) {
            setOpen(false);
          }
        }
        break;
      }
      case "Escape":
        event.preventDefault();
        setOpen(false);
        break;
      case "Tab":
        setOpen(false);
        break;
      default:
        if (event.key.length === 1) {
          const now = Date.now();
          const store = typeahead.current;
          store.query = now - store.at > TYPEAHEAD_RESET_MS ? event.key : store.query + event.key;
          store.at = now;
          const match = options.findIndex((option) =>
            option.label.toLowerCase().startsWith(store.query.toLowerCase())
          );
          if (match >= 0) {
            setActive(match);
          }
        }
    }
  };

  return { open, setOpen, active, setActive, rootRef, handleKeyDown };
}

function Popover({
  id,
  options,
  active,
  isSelected,
  onHover,
  onPick
}: {
  readonly id: string;
  readonly options: readonly ControlOption[];
  readonly active: number;
  readonly isSelected: (value: string) => boolean;
  readonly onHover: (index: number) => void;
  readonly onPick: (value: string) => void;
}) {
  // role="listbox"/"option" carry the semantics; the trigger button owns focus and
  // aria-activedescendant (the WAI-ARIA listbox pattern), so options are tabIndex -1.
  return (
    <div className="ui-select__pop" id={`${id}-list`} role="listbox">
      {options.length === 0 ? <p className="ui-select__empty">No options</p> : null}
      {options.map((option, index) => {
        const selected = isSelected(option.value);
        const classes = ["ui-select__opt"];
        if (index === active) {
          classes.push("is-active");
        }
        if (selected) {
          classes.push("is-selected");
        }
        return (
          <div
            aria-selected={selected}
            className={classes.join(" ")}
            id={`${id}-opt-${index}`}
            key={option.value}
            onMouseDown={(event) => {
              event.preventDefault();
              onPick(option.value);
            }}
            onMouseEnter={() => onHover(index)}
            role="option"
            tabIndex={-1}
          >
            <span className="ui-select__opt-label">{option.label}</span>
            {selected ? <Check aria-hidden="true" size={14} /> : null}
          </div>
        );
      })}
    </div>
  );
}

export function Select({
  value,
  options,
  onChange,
  placeholder = "Select",
  ariaLabel,
  disabled = false
}: {
  readonly value: string;
  readonly options: readonly ControlOption[];
  readonly onChange: (value: string) => void;
  readonly placeholder?: string;
  readonly ariaLabel?: string;
  readonly disabled?: boolean;
}) {
  const id = useId();
  const listbox = useListbox(options, (next) => onChange(next));
  const current = options.find((option) => option.value === value);
  return (
    <div className="ui-select" ref={listbox.rootRef}>
      <button
        aria-activedescendant={listbox.open ? `${id}-opt-${listbox.active}` : undefined}
        aria-controls={listbox.open ? `${id}-list` : undefined}
        aria-expanded={listbox.open}
        aria-haspopup="listbox"
        aria-label={ariaLabel}
        className="ui-select__btn"
        disabled={disabled}
        onClick={() => listbox.setOpen(!listbox.open)}
        onKeyDown={(event) => listbox.handleKeyDown(event, true)}
        role="combobox"
        type="button"
      >
        <span className={`ui-select__value${current ? "" : " is-placeholder"}`}>
          {current?.label ?? placeholder}
        </span>
        <ChevronDown aria-hidden="true" className="ui-select__chev" size={15} />
      </button>
      {listbox.open ? (
        <Popover
          active={listbox.active}
          id={id}
          isSelected={(candidate) => candidate === value}
          onHover={listbox.setActive}
          onPick={(next) => {
            onChange(next);
            listbox.setOpen(false);
          }}
          options={options}
        />
      ) : null}
    </div>
  );
}

export function MultiSelect({
  values,
  options,
  onToggle,
  placeholder = "Any",
  ariaLabel,
  trigger
}: {
  readonly values: readonly string[];
  readonly options: readonly ControlOption[];
  readonly onToggle: (value: string) => void;
  readonly placeholder?: string;
  readonly ariaLabel?: string;
  readonly trigger?: ReactNode;
}) {
  const id = useId();
  const selectedSet = new Set(values);
  const listbox = useListbox(options, (next) => onToggle(next));
  const label = values.length > 0 ? `${values.length} selected` : placeholder;
  return (
    <div className="ui-select ui-select--multi" ref={listbox.rootRef}>
      <button
        aria-activedescendant={listbox.open ? `${id}-opt-${listbox.active}` : undefined}
        aria-controls={listbox.open ? `${id}-list` : undefined}
        aria-expanded={listbox.open}
        aria-haspopup="listbox"
        aria-label={ariaLabel}
        className={`ui-select__btn${values.length > 0 ? " has-value" : ""}`}
        onClick={() => listbox.setOpen(!listbox.open)}
        onKeyDown={(event) => listbox.handleKeyDown(event, false)}
        role="combobox"
        type="button"
      >
        {trigger ?? <span className="ui-select__value">{label}</span>}
        <ChevronDown aria-hidden="true" className="ui-select__chev" size={15} />
      </button>
      {listbox.open ? (
        <Popover
          active={listbox.active}
          id={id}
          isSelected={(candidate) => selectedSet.has(candidate)}
          onHover={listbox.setActive}
          onPick={onToggle}
          options={options}
        />
      ) : null}
    </div>
  );
}
