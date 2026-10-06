{#- Division that returns NULL instead of erroring when the denominator is zero. -#}
{% macro safe_div(numerator, denominator) -%}
    ({{ numerator }}) / nullif(({{ denominator }}), 0)
{%- endmacro %}

{#- Per-member-per-month: numerator / member months. -#}
{% macro pmpm(numerator, member_months='member_months') -%}
    {{ safe_div(numerator, member_months) }}
{%- endmacro %}
