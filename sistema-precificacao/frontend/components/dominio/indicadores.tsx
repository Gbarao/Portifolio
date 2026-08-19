/**
 * Componentes que carregam significado do dominio.
 *
 * Nao sao enfeite: a especificacao exige feedback visual para regra fiscal
 * vencida, calculo provisorio e margem abaixo do preco sustentavel. Aqui essas
 * regras viram cor, icone e texto -- sempre com o texto, nunca so a cor.
 */

import {
  AlertTriangle,
  Ban,
  CircleCheck,
  CircleHelp,
  Clock,
  Info,
  TriangleAlert,
} from "lucide-react";
import * as React from "react";

import { Distintivo, type TomDistintivo } from "@/components/ui/primitivos";
import { percentual, precoUnitario } from "@/lib/formato";
import { cx } from "@/lib/utilitarios";
import type { CamadaPreco, StatusDado, StatusRegraFiscal } from "@/lib/tipos";

/* ------------------------------------------------------- Status de um dado */

const STATUS_DADO: Record<
  StatusDado,
  { tom: TomDistintivo; texto: string; Icone: typeof CircleCheck }
> = {
  CONFIRMADO: { tom: "ok", texto: "Confirmado", Icone: CircleCheck },
  ESTIMADO: { tom: "info", texto: "Estimado", Icone: Info },
  PROVISORIO: { tom: "atencao", texto: "Provisório", Icone: Clock },
  VENCIDO: { tom: "critico", texto: "Vencido", Icone: TriangleAlert },
  INCONSISTENTE: { tom: "critico", texto: "Inconsistente", Icone: Ban },
};

export function StatusDadoBadge({ status }: { status: StatusDado }) {
  const config = STATUS_DADO[status] ?? {
    tom: "neutro" as TomDistintivo,
    texto: status,
    Icone: CircleHelp,
  };
  const { Icone } = config;
  return (
    <Distintivo tom={config.tom}>
      <Icone className="size-3" aria-hidden />
      {config.texto}
    </Distintivo>
  );
}

/* ------------------------------------------------------ Status de uma regra */

const STATUS_FISCAL: Record<
  StatusRegraFiscal,
  { tom: TomDistintivo; texto: string; Icone: typeof CircleCheck }
> = {
  VALIDADA: { tom: "ok", texto: "Validada", Icone: CircleCheck },
  PROVISORIA: { tom: "atencao", texto: "Provisória", Icone: Clock },
  VENCIDA: { tom: "critico", texto: "Vencida", Icone: TriangleAlert },
  BLOQUEADA: { tom: "critico", texto: "Bloqueada", Icone: Ban },
};

export function StatusFiscalBadge({ status }: { status: StatusRegraFiscal }) {
  const config = STATUS_FISCAL[status] ?? {
    tom: "neutro" as TomDistintivo,
    texto: status,
    Icone: CircleHelp,
  };
  const { Icone } = config;
  return (
    <Distintivo tom={config.tom}>
      <Icone className="size-3" aria-hidden />
      {config.texto}
    </Distintivo>
  );
}

/* ------------------------------------------------------- Camadas de preco */

export const CAMADAS: Record<
  CamadaPreco,
  { rotulo: string; cor: string; finalidade: string }
> = {
  CAIXA: {
    rotulo: "Caixa",
    cor: "var(--color-camada-caixa)",
    finalidade: "Decisão excepcional, validade curta",
  },
  CONTRIBUICAO: {
    rotulo: "Contribuição",
    cor: "var(--color-camada-contribuicao)",
    finalidade: "Ocupação de capacidade ociosa",
  },
  OPERACIONAL: {
    rotulo: "Operacional",
    cor: "var(--color-camada-operacional)",
    finalidade: "Avaliação de eficiência",
  },
  SUSTENTAVEL: {
    rotulo: "Sustentável",
    cor: "var(--color-camada-sustentavel)",
    finalidade: "Piso normal de negociação",
  },
  ALVO: {
    rotulo: "Alvo",
    cor: "var(--color-camada-alvo)",
    finalidade: "Proposta comercial padrão",
  },
  MERCADO_COMPARAVEL: {
    rotulo: "Mercado",
    cor: "var(--color-camada-mercado)",
    finalidade: "Teste de competitividade",
  },
};

export function CamadaBadge({ camada }: { camada: CamadaPreco }) {
  const config = CAMADAS[camada];
  return (
    <span className="inline-flex items-center gap-1.5 text-xs font-medium">
      <span
        className="size-2 rounded-full"
        style={{ background: config?.cor }}
        aria-hidden
      />
      {config?.rotulo ?? camada}
    </span>
  );
}

/* ------------------------------------------------------------ Alertas */

export type SeveridadeAlerta = "info" | "atencao" | "critico";

const ALERTA: Record<SeveridadeAlerta, { classe: string; Icone: typeof Info }> = {
  info: { classe: "border-info/30 bg-info-fundo text-info", Icone: Info },
  atencao: {
    classe: "border-atencao/35 bg-atencao-fundo text-atencao",
    Icone: AlertTriangle,
  },
  critico: {
    classe: "border-critico/30 bg-critico-fundo text-critico",
    Icone: TriangleAlert,
  },
};

export function Alerta({
  severidade = "atencao",
  titulo,
  children,
  className,
}: {
  severidade?: SeveridadeAlerta;
  titulo?: string;
  children: React.ReactNode;
  className?: string;
}) {
  const { classe, Icone } = ALERTA[severidade];
  return (
    <div
      role={severidade === "critico" ? "alert" : "status"}
      className={cx("flex gap-3 rounded-lg border px-4 py-3 text-sm", classe, className)}
    >
      <Icone className="mt-0.5 size-4 shrink-0" aria-hidden />
      <div className="min-w-0 space-y-1">
        {titulo ? <p className="font-medium">{titulo}</p> : null}
        <div className="text-texto">{children}</div>
      </div>
    </div>
  );
}

/** Lista de alertas vinda da API; some quando nao ha nenhum. */
export function ListaAlertas({
  alertas,
  severidade = "atencao",
}: {
  alertas: string[];
  severidade?: SeveridadeAlerta;
}) {
  if (!alertas.length) return null;
  return (
    <Alerta severidade={severidade} titulo={`${alertas.length} alerta(s) do cálculo`}>
      <ul className="list-disc space-y-1 pl-4">
        {alertas.map((alerta) => (
          <li key={alerta}>{alerta}</li>
        ))}
      </ul>
    </Alerta>
  );
}

/* ---------------------------------------------------------- Indicador seco */

export function Indicador({
  rotulo,
  valor,
  detalhe,
  destaque,
}: {
  rotulo: string;
  valor: React.ReactNode;
  detalhe?: React.ReactNode;
  destaque?: boolean;
}) {
  return (
    <div className="space-y-1">
      <p className="text-xs font-medium tracking-wide text-texto-tenue uppercase">
        {rotulo}
      </p>
      <p
        className={cx(
          "numerico font-semibold tracking-tight",
          destaque ? "text-2xl" : "text-lg",
        )}
      >
        {valor}
      </p>
      {detalhe ? <p className="text-xs text-texto-suave">{detalhe}</p> : null}
    </div>
  );
}

/** Barra comparativa das camadas de preco, do caixa ao alvo. */
export function BarraCamadas({
  valores,
}: {
  valores: { camada: CamadaPreco; valor: string }[];
}) {
  const maximo = Math.max(...valores.map((v) => Number(v.valor)), 0) || 1;

  return (
    <div className="space-y-2">
      {valores.map(({ camada, valor }) => {
        const config = CAMADAS[camada];
        const largura = (Number(valor) / maximo) * 100;
        return (
          <div key={camada} className="grid grid-cols-[8rem_1fr_6rem] items-center gap-3">
            <CamadaBadge camada={camada} />
            <div className="h-2 overflow-hidden rounded-full bg-fundo-sutil">
              <div
                className="h-full rounded-full transition-all"
                style={{ width: `${largura}%`, background: config?.cor }}
              />
            </div>
            <span className="numerico text-right text-sm">{precoUnitario(valor)}</span>
          </div>
        );
      })}
    </div>
  );
}

export function Rendimento({ valor }: { valor: string }) {
  const numero = Number(valor);
  const tom: TomDistintivo =
    numero >= 0.9 ? "ok" : numero >= 0.8 ? "atencao" : "critico";
  return <Distintivo tom={tom}>{percentual(valor, 2)}</Distintivo>;
}
