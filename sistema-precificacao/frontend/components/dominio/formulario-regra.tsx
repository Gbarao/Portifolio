"use client";

/**
 * Formulario de regra tributaria.
 *
 * Serve a tres operacoes que a especificacao trata como distintas:
 * criar, editar uma regra ainda provisoria e abrir nova vigencia de uma
 * regra ja validada. A diferenca nao e cosmetica -- editar uma regra
 * validada apagaria a base de um preco ja praticado.
 */

import * as React from "react";

import { Alerta } from "@/components/dominio/indicadores";
import {
  Botao,
  Campo,
  Entrada,
  Selecao,
} from "@/components/ui/primitivos";
import { ErroApi, api } from "@/lib/api";
import type { RegraTributaria } from "@/lib/tipos";

export type ModoFormulario = "criar" | "editar" | "nova-vigencia";

const TRIBUTOS = [
  "ICMS",
  "ICMS_ST",
  "DIFAL",
  "IPI",
  "PIS",
  "COFINS",
  "ISS",
  "IRPJ",
  "CSLL",
  "INSS_RETENCAO",
  "DAS_SIMPLES",
  "CBS",
  "IBS",
  "IMPOSTO_SELETIVO",
];

const OPERACOES = [
  "VENDA",
  "COMPRA",
  "INDUSTRIALIZACAO",
  "SERVICO",
  "BONIFICACAO",
  "DEVOLUCAO",
  "TRANSFERENCIA",
  "FRETE",
];

const TRATAMENTOS = [
  "DEBITO",
  "CREDITO",
  "ISENCAO",
  "SUSPENSAO",
  "DIFERIMENTO",
  "SUBSTITUICAO_TRIBUTARIA",
  "RETENCAO",
  "REDUCAO_BASE",
  "NAO_TRIBUTADO",
  "CREDITO_PRESUMIDO",
];

const RECUPERABILIDADES = [
  "NAO_APLICAVEL",
  "ELEGIVEL",
  "VEDADA",
  "PROPORCIONAL",
  "CONDICIONADA",
];

const FORMAS_BASE = [
  "POR_FORA",
  "POR_DENTRO",
  "BASE_REDUZIDA",
  "VALOR_FIXO",
  "PAUTA",
];

const REGIMES = ["LUCRO_REAL", "LUCRO_PRESUMIDO", "SIMPLES_NACIONAL"];

interface Estado {
  codigo: string;
  descricao: string;
  tributo: string;
  tipo_operacao: string;
  regime_tributario: string;
  vigencia_inicio: string;
  fundamento_legal: string;
  forma_calculo_base: string;
  aliquota: string;
  percentual_reducao_base: string;
  percentual_presuncao_base: string;
  tratamento: string;
  recuperabilidade: string;
  percentual_recuperavel: string;
  prazo_realizacao_credito_dias: string;
  ncm: string;
  cfop: string;
  uf_origem: string;
  uf_destino: string;
  regime_parceiro: string;
  compoe_deducao_venda: boolean;
  gera_credito_compra: boolean;
  compoe_custo_nao_recuperavel: boolean;
  incide_sobre_lucro: boolean;
  requer_confirmacao_condicao: boolean;
  condicao_descricao: string;
  motivo: string;
}

function estadoInicial(regra?: RegraTributaria | null): Estado {
  return {
    codigo: regra?.codigo ?? "",
    descricao: regra?.descricao ?? "",
    tributo: regra?.tributo ?? "ICMS",
    tipo_operacao: regra?.tipo_operacao ?? "VENDA",
    regime_tributario: regra?.regime_tributario ?? "",
    vigencia_inicio: regra?.vigencia_inicio ?? new Date().toISOString().slice(0, 10),
    fundamento_legal: regra?.fundamento_legal ?? "",
    forma_calculo_base: "POR_DENTRO",
    aliquota: regra?.aliquota ?? "",
    percentual_reducao_base: "",
    percentual_presuncao_base: regra?.percentual_presuncao_base ?? "",
    tratamento: regra?.tratamento ?? "DEBITO",
    recuperabilidade: regra?.recuperabilidade ?? "NAO_APLICAVEL",
    percentual_recuperavel: "",
    prazo_realizacao_credito_dias: "",
    ncm: "",
    cfop: "",
    uf_origem: "",
    uf_destino: "",
    regime_parceiro: "",
    compoe_deducao_venda: regra?.compoe_deducao_venda ?? false,
    gera_credito_compra: regra?.gera_credito_compra ?? false,
    compoe_custo_nao_recuperavel: false,
    incide_sobre_lucro: regra?.incide_sobre_lucro ?? false,
    requer_confirmacao_condicao: regra?.requer_confirmacao_condicao ?? false,
    condicao_descricao: regra?.condicao_descricao ?? "",
    motivo: "",
  };
}

/** Só envia campo preenchido: string vazia vira ausência, não zero. */
function corpoDe(estado: Estado, modo: ModoFormulario) {
  const opcional = (valor: string) => (valor.trim() === "" ? null : valor.trim());

  const base: Record<string, unknown> = {
    descricao: estado.descricao,
    tributo: estado.tributo,
    tipo_operacao: estado.tipo_operacao,
    regime_tributario: opcional(estado.regime_tributario),
    vigencia_inicio: estado.vigencia_inicio,
    fundamento_legal: estado.fundamento_legal,
    forma_calculo_base: estado.forma_calculo_base,
    aliquota: opcional(estado.aliquota),
    percentual_reducao_base: opcional(estado.percentual_reducao_base),
    percentual_presuncao_base: opcional(estado.percentual_presuncao_base),
    tratamento: estado.tratamento,
    recuperabilidade: estado.recuperabilidade,
    percentual_recuperavel: opcional(estado.percentual_recuperavel),
    prazo_realizacao_credito_dias: estado.prazo_realizacao_credito_dias
      ? Number(estado.prazo_realizacao_credito_dias)
      : null,
    ncm: opcional(estado.ncm),
    cfop: opcional(estado.cfop),
    uf_origem: opcional(estado.uf_origem),
    uf_destino: opcional(estado.uf_destino),
    regime_parceiro: opcional(estado.regime_parceiro),
    compoe_deducao_venda: estado.compoe_deducao_venda,
    gera_credito_compra: estado.gera_credito_compra,
    compoe_custo_nao_recuperavel: estado.compoe_custo_nao_recuperavel,
    incide_sobre_lucro: estado.incide_sobre_lucro,
    requer_confirmacao_condicao: estado.requer_confirmacao_condicao,
    condicao_descricao: opcional(estado.condicao_descricao),
  };

  if (modo === "criar") return { ...base, codigo: estado.codigo };
  if (modo === "nova-vigencia") return { ...base, motivo: estado.motivo };
  return base;
}

export function FormularioRegra({
  modo,
  regra,
  aoConcluir,
  aoCancelar,
}: {
  modo: ModoFormulario;
  regra?: RegraTributaria | null;
  aoConcluir: () => void;
  aoCancelar: () => void;
}) {
  const [estado, setEstado] = React.useState<Estado>(() => estadoInicial(regra));
  const [erro, setErro] = React.useState<string | null>(null);
  const [salvando, setSalvando] = React.useState(false);

  const campo = (nome: keyof Estado) => ({
    value: String(estado[nome] ?? ""),
    onChange: (
      evento: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>,
    ) => setEstado((e) => ({ ...e, [nome]: evento.target.value })),
  });

  const marcavel = (nome: keyof Estado) => ({
    checked: Boolean(estado[nome]),
    onChange: (evento: React.ChangeEvent<HTMLInputElement>) =>
      setEstado((e) => ({ ...e, [nome]: evento.target.checked })),
  });

  async function salvar(evento: React.FormEvent) {
    evento.preventDefault();
    setSalvando(true);
    setErro(null);
    try {
      const corpo = corpoDe(estado, modo);
      if (modo === "criar") {
        await api.post("/tributario/regras", corpo);
      } else if (modo === "nova-vigencia") {
        await api.post(`/tributario/regras/${regra?.id}/vigencias`, corpo);
      } else {
        await api.patch(`/tributario/regras/${regra?.id}`, corpo);
      }
      aoConcluir();
    } catch (e) {
      setErro(e instanceof ErroApi ? e.message : String(e));
    } finally {
      setSalvando(false);
    }
  }

  return (
    <form onSubmit={salvar} className="space-y-5">
      {modo === "nova-vigencia" ? (
        <Alerta severidade="info" titulo="Nova vigência">
          A regra atual será encerrada no dia anterior ao início desta, e a nova
          nascerá <strong>provisória</strong>: mudar o número invalida a
          validação que se referia ao número anterior.
        </Alerta>
      ) : null}

      {erro ? (
        <Alerta severidade="critico" titulo="Não foi possível salvar">
          {erro}
        </Alerta>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2">
        {modo === "criar" ? (
          <Campo rotulo="Código" dica="Identificador interno, ex.: LR-VENDA-PIS">
            <Entrada required {...campo("codigo")} />
          </Campo>
        ) : null}

        <Campo rotulo="Descrição">
          <Entrada required {...campo("descricao")} />
        </Campo>

        <Campo rotulo="Tributo">
          <Selecao {...campo("tributo")}>
            {TRIBUTOS.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </Selecao>
        </Campo>

        <Campo rotulo="Operação">
          <Selecao {...campo("tipo_operacao")}>
            {OPERACOES.map((o) => (
              <option key={o} value={o}>
                {o}
              </option>
            ))}
          </Selecao>
        </Campo>

        <Campo rotulo="Regime da empresa" dica="Em branco = vale para todos">
          <Selecao {...campo("regime_tributario")}>
            <option value="">Todos os regimes</option>
            {REGIMES.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </Selecao>
        </Campo>

        <Campo
          rotulo={modo === "nova-vigencia" ? "Início da nova vigência" : "Início da vigência"}
        >
          <Entrada type="date" required {...campo("vigencia_inicio")} />
        </Campo>
      </div>

      <fieldset className="space-y-4 rounded-lg border border-borda p-4">
        <legend className="px-1 text-xs font-medium tracking-wide text-texto-tenue uppercase">
          Cálculo
        </legend>
        <div className="grid gap-4 sm:grid-cols-2">
          <Campo
            rotulo="Forma da base"
            dica="Por dentro, por fora, reduzida, presumida, pauta ou valor fixo"
          >
            <Selecao {...campo("forma_calculo_base")}>
              {FORMAS_BASE.map((f) => (
                <option key={f} value={f}>
                  {f}
                </option>
              ))}
            </Selecao>
          </Campo>

          <Campo rotulo="Alíquota" dica="Fração decimal: 0,0925 = 9,25%">
            <Entrada inputMode="decimal" placeholder="0.0925" {...campo("aliquota")} />
          </Campo>

          <Campo rotulo="Redução da base" dica="Fração; deixe vazio se não houver">
            <Entrada inputMode="decimal" {...campo("percentual_reducao_base")} />
          </Campo>

          <Campo
            rotulo="Presunção da base"
            dica="Lucro Presumido: 0,08 para mercadorias"
          >
            <Entrada inputMode="decimal" {...campo("percentual_presuncao_base")} />
          </Campo>

          <Campo rotulo="Tratamento">
            <Selecao {...campo("tratamento")}>
              {TRATAMENTOS.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </Selecao>
          </Campo>

          <Campo rotulo="Recuperabilidade">
            <Selecao {...campo("recuperabilidade")}>
              {RECUPERABILIDADES.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </Selecao>
          </Campo>
        </div>
      </fieldset>

      <fieldset className="space-y-3 rounded-lg border border-borda p-4">
        <legend className="px-1 text-xs font-medium tracking-wide text-texto-tenue uppercase">
          Efeito econômico
        </legend>
        <p className="text-xs text-texto-suave">
          São estas marcações que dizem ao motor o que fazer com o tributo. Elas
          decidem o preço.
        </p>
        <label className="flex items-start gap-2 text-sm">
          <input type="checkbox" className="mt-1" {...marcavel("compoe_deducao_venda")} />
          <span>
            <strong>Deduz do preço (entra em r)</strong>
            <span className="block text-xs text-texto-suave">
              Tributos sobre a venda e, no Lucro Presumido, a presunção de
              IRPJ/CSLL.
            </span>
          </span>
        </label>
        <label className="flex items-start gap-2 text-sm">
          <input type="checkbox" className="mt-1" {...marcavel("gera_credito_compra")} />
          <span>
            <strong>Gera crédito na compra</strong>
            <span className="block text-xs text-texto-suave">
              Só reduz o custo quando a recuperabilidade for elegível.
            </span>
          </span>
        </label>
        <label className="flex items-start gap-2 text-sm">
          <input
            type="checkbox"
            className="mt-1"
            {...marcavel("compoe_custo_nao_recuperavel")}
          />
          <span>
            <strong>Compõe custo não recuperável</strong>
            <span className="block text-xs text-texto-suave">
              Regimes cumulativos: o tributo embutido na compra vira custo.
            </span>
          </span>
        </label>
        <label className="flex items-start gap-2 text-sm">
          <input type="checkbox" className="mt-1" {...marcavel("incide_sobre_lucro")} />
          <span>
            <strong>Incide sobre o lucro</strong>
            <span className="block text-xs text-texto-suave">
              IRPJ/CSLL no Lucro Real: ficam fora de r, e a margem-alvo é
              pré-tributo.
            </span>
          </span>
        </label>
        <label className="flex items-start gap-2 text-sm">
          <input
            type="checkbox"
            className="mt-1"
            {...marcavel("requer_confirmacao_condicao")}
          />
          <span>
            <strong>Condicional</strong>
            <span className="block text-xs text-texto-suave">
              Gera alerta e não abate crédito até a condição ser confirmada.
            </span>
          </span>
        </label>
        {estado.requer_confirmacao_condicao ? (
          <Campo rotulo="Qual é a condição">
            <Entrada
              placeholder="Ex.: adquirente no lucro real usando o material como matéria-prima"
              {...campo("condicao_descricao")}
            />
          </Campo>
        ) : null}
      </fieldset>

      <details className="rounded-lg border border-borda p-4">
        <summary className="cursor-pointer text-sm font-medium">
          Chaves de aplicação (opcionais)
        </summary>
        <p className="mt-2 mb-4 text-xs text-texto-suave">
          Campo em branco funciona como coringa. Entre as regras compatíveis,
          vence a que tem mais chaves preenchidas.
        </p>
        <div className="grid gap-4 sm:grid-cols-2">
          <Campo rotulo="NCM">
            <Entrada {...campo("ncm")} />
          </Campo>
          <Campo rotulo="CFOP">
            <Entrada {...campo("cfop")} />
          </Campo>
          <Campo rotulo="UF de origem">
            <Entrada maxLength={2} {...campo("uf_origem")} />
          </Campo>
          <Campo rotulo="UF de destino">
            <Entrada maxLength={2} {...campo("uf_destino")} />
          </Campo>
          <Campo rotulo="Regime do parceiro">
            <Selecao {...campo("regime_parceiro")}>
              <option value="">Qualquer</option>
              {REGIMES.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </Selecao>
          </Campo>
        </div>
      </details>

      <Campo
        rotulo="Fundamento legal"
        dica="Obrigatório: toda regra cita a norma que a sustenta"
      >
        <Entrada required {...campo("fundamento_legal")} />
      </Campo>

      {modo === "nova-vigencia" ? (
        <Campo rotulo="Motivo da mudança" dica="Fica registrado na regra sucessora">
          <Entrada required {...campo("motivo")} />
        </Campo>
      ) : null}

      <div className="flex justify-end gap-2 border-t border-borda pt-4">
        <Botao type="button" variante="secundario" onClick={aoCancelar}>
          Cancelar
        </Botao>
        <Botao type="submit" disabled={salvando}>
          {salvando
            ? "Salvando…"
            : modo === "criar"
              ? "Criar regra"
              : modo === "nova-vigencia"
                ? "Abrir nova vigência"
                : "Salvar alterações"}
        </Botao>
      </div>
    </form>
  );
}
