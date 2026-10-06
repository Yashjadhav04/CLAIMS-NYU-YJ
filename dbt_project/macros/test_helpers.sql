{#-
  Claims whose derived benefit phase can be trusted.

  Phase is derived from cumulative claims received so far. It is wrong for a claim if earlier claims for the same member
  and year have not reached the data set: (a) unresolved CMS rejections, or (b) claims not yet received (only possible for
  fills in the last ~90 days before the extract date, given the submission-lag distribution). This macro removes both
  populations so phase-consistency tests are exact. Those excluded populations are themselves a real-world data risk
  (documented in docs/ASSUMPTIONS.md).
-#}
{% macro claims_with_complete_history() -%}
(
    select f.*
    from {{ ref('fct_pde_claims') }} f
    where f.fill_date < cast('{{ var("as_of_date") }}' as date) - 95
      and not exists (
          select 1
          from {{ ref('int_pde_rejects') }} r
          join {{ ref('stg_pde_submissions') }} s
            on s.claim_group_id = r.claim_group_id and s.dcs_status = 'R'
          where not r.is_resolved
            and s.member_id = f.member_id
            and extract(year from s.fill_date) = f.benefit_year
      )
)
{%- endmacro %}
