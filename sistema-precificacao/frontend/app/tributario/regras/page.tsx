"use client";

/**
 * Matriz de regras tributarias -- consulta e manutencao.
 *
 * A tela distingue tres operacoes que a especificacao trata como diferentes:
 * criar, editar uma regra provisoria e abrir nova vigencia de uma validada.
 * Regra validada nao e editada no lugar: ela pode ter sustentado uma cotacao.
 */

import { Pencil, Plus, ShieldCheck, SquareStack, X } from "lucide-react";
import * as React from "react";

import {
  Alerta,
  StatusFiscalBadge,
} from "@/components/dominio/indicadores";
import {
  FormularioRegra,
  type ModoFormulario,
} from "@/components/dominio/formulario-regra";
import { CabecalhoPagina } from "@/components/layout/pagina";
import {
  Botao,
  Campo,
  Cartao,
  Distintivo,
  Entrada,
  LinhaTabela,
  Tabela,
  Td,
  Th,
  Vazio,
} from "@/components/ui/primitivos";
import { ErroApi, api } from "@/lib/api";
import { percentual, rotulo, vigencia } from "@/lib/formato";
import type { Pagina, RegraTributaria } from "@/lib/tipos";

function EfeitoDaRegra({ regra }: { regra: RegraTributaria }) {
  if (regra.compoe_deducao_venda) {
    return <Distintivo tom="atencao">Deduz do preço (r)</Distintivo>;
  }
  if (regra.gera_credito_compra) {
    return <Distintivo tom="ok">Credita na compra</Distintivo>;
  }
  if (regra.incide_sobre_lucro) {
    return <Distintivo tom="info">Incide sobre o lucro</Distintivo>;
  }
  return <Distintivo tom="neutro">Sem efeito em r</Distintivo>;
}

/** Painel lateral: mantém a lista visível enquanto se edita. */
function Painel({
  titulo,
  descricao,
  aoFechar,
  children,
}: {
  titulo: string;
  descricao?: string;
  aoFechar: () => void;
  children: React.ReactNode;
}) {
  React.useEffect(() => {
    const aoTeclar = (evento: KeyboardEvent) => {
      if (evento.key === "Escape") aoFechar();
    };
    window.addEventListener("keydown", aoTeclar);

    const overflowAnterior = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    return () => {
      window.removeEventListener("keydown", aoTeclar);
      document.body.style.overflow = overflowAnterior;
    };
  }, [aoFechar]);

  return (
    <div className="fixed inset-0 z-30 flex justify-end">
      <div
        className="absolute inset-0 bg-black/30"
        onClick={aoFechar}
        aria-hidden
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={titulo}
        className="relative flex h-full w-full max-w-2xl flex-col overflow-y-auto border-l border-borda bg-fundo-elevado shadow-xl"
      >
        <header className="sticky top-0 flex items-start justify-between gap-4 border-b border-borda bg-fundo-elevado px-6 py-4">
          <div>
            <h2 className="text-sm font-semibold">{titulo}</h2>
            {descricao ? (
              <p className="mt-1 text-sm text-texto-suave">{descricao}</p>
            ) : null}
          </div>
          <Botao
            variante="fantasma"
            tamanho="sm"
            onClick={aoFechar}
            aria-label="Fechar"
          >
            <X className="size-4" aria-hidden />
          </Botao>
        </header>
        <div className="px-6 py-5">{children}</div>
      </div>
    </div>
  );
}

export default function PaginaRegras() {
  const [regras, setRegras] = React.useState<RegraTributaria[]>([]);
  const [erro, setErro] = React.useState<string | null>(null);
  const [carregando, setCarregando] = React.useState(true);
  const [aviso, setAviso] = React.useState<string | null>(null);

  const [painel, setPainel] = React.useState<{
    modo: ModoFormulario | "validar" | "encerrar";
    regra?: RegraTributaria | null;
  } | null>(null);

  const carregar = React.useCallback(async () => {
    setCarregando(true);
    try {
      const pagina = await api.lista<RegraTributaria>(
        "/tributario/regras?limite=200",
      );
      setRegras((pagina as Pagina<RegraTributaria>).itens);
      setErro(null);
    } catch (e) {
      setErro(e instanceof ErroApi ? e.message : String(e));
    } finally {
      setCarregando(false);
    }
  }, []);

  React.useEffect(() => {
    void carregar();
  }, [carregar]);

  function concluir(mensagem: string) {
    setPainel(null);
    setAviso(mensagem);
    void carregar();
  }

  const provisorias = regras.filter((r) => r.status === "PROVISORIA").length;

  return (
    <>
      <CabecalhoPagina
        titulo="Matriz de regras tributárias"
        descricao="Regras versionadas por vigência. A regra aplicada é escolhida pela data da operação, nunca pela data de hoje."
        acoes={
          <Botao onClick={() => setPainel({ modo: "criar" })}>
            <Plus className="size-4" aria-hidden />
            Nova regra
          </Botao>
        }
      />

      {aviso ? (
        <Alerta severidade="info" className="mb-6">
          {aviso}
        </Alerta>
      ) : null}

      {erro ? (
        <Alerta severidade="critico" titulo="Não foi possível carregar" className="mb-6">
          {erro}
        </Alerta>
      ) : null}

      {provisorias > 0 ? (
        <Alerta
          severidade="atencao"
          titulo={`${provisorias} de ${regras.length} regras ainda provisórias`}
          className="mb-6"
        >
          Enquanto o responsável fiscal não validar cada regra, nenhuma cotação
          pode ser classificada como definitiva — mesmo com todos os demais
          campos preenchidos.
        </Alerta>
      ) : null}

      <Cartao>
        {regras.length === 0 && !carregando ? (
          <Vazio
            titulo="Nenhuma regra cadastrada"
            descricao="Sem matriz tributária o sistema não fecha cotação definitiva."
            acao={
              <Botao onClick={() => setPainel({ modo: "criar" })}>Criar a primeira</Botao>
            }
          />
        ) : (
          <Tabela>
            <thead>
              <tr>
                <Th>Código</Th>
                <Th>Tributo</Th>
                <Th>Operação</Th>
                <Th>Regime</Th>
                <Th numerica>Alíquota</Th>
                <Th>Efeito</Th>
                <Th>Vigência</Th>
                <Th>Status</Th>
                <Th />
              </tr>
            </thead>
            <tbody>
              {regras.map((regra) => (
                <LinhaTabela key={regra.id}>
                  <Td className="font-mono text-xs whitespace-nowrap">
                    {regra.codigo}
                    {regra.versao > 1 ? (
                      <span className="ml-1 text-texto-tenue">v{regra.versao}</span>
                    ) : null}
                  </Td>
                  <Td className="font-medium">{regra.tributo}</Td>
                  <Td className="text-texto-suave">{rotulo(regra.tipo_operacao)}</Td>
                  <Td className="text-texto-suave">
                    {regra.regime_tributario ? rotulo(regra.regime_tributario) : "Todos"}
                  </Td>
                  <Td numerica>
                    {regra.percentual_presuncao_base && regra.aliquota
                      ? `${percentual(regra.percentual_presuncao_base, 0)} × ${percentual(regra.aliquota, 0)}`
                      : regra.aliquota
                        ? percentual(regra.aliquota)
                        : "por faixa"}
                  </Td>
                  <Td>
                    <EfeitoDaRegra regra={regra} />
                  </Td>
                  <Td className="text-xs text-texto-suave">
                    {vigencia(regra.vigencia_inicio, regra.vigencia_fim)}
                  </Td>
                  <Td>
                    <StatusFiscalBadge status={regra.status} />
                  </Td>
                  <Td className="text-right whitespace-nowrap">
                    {regra.status === "PROVISORIA" ? (
                      <>
                        <Botao
                          variante="fantasma"
                          tamanho="sm"
                          onClick={() => setPainel({ modo: "editar", regra })}
                          aria-label={`Editar ${regra.codigo}`}
                        >
                          <Pencil className="size-3.5" aria-hidden />
                          Editar
                        </Botao>
                        <Botao
                          variante="fantasma"
                          tamanho="sm"
                          onClick={() => setPainel({ modo: "validar", regra })}
                          aria-label={`Validar ${regra.codigo}`}
                        >
                          <ShieldCheck className="size-3.5" aria-hidden />
                          Validar
                        </Botao>
                      </>
                    ) : (
                      <Botao
                        variante="fantasma"
                        tamanho="sm"
                        onClick={() => setPainel({ modo: "nova-vigencia", regra })}
                        aria-label={`Nova vigência de ${regra.codigo}`}
                      >
                        <SquareStack className="size-3.5" aria-hidden />
                        Nova vigência
                      </Botao>
                    )}
                    <Botao
                      variante="fantasma"
                      tamanho="sm"
                      onClick={() => setPainel({ modo: "encerrar", regra })}
                      aria-label={`Encerrar ${regra.codigo}`}
                    >
                      Encerrar
                    </Botao>
                  </Td>
                </LinhaTabela>
              ))}
            </tbody>
          </Tabela>
        )}
      </Cartao>

      <p className="mt-3 text-xs text-texto-tenue">
        Regra validada não pode ser editada no lugar: ela já pode ter sustentado
        um preço praticado. Para alterá-la, abra uma nova vigência — a anterior
        fica no histórico e as cotações antigas continuam reproduzíveis.
      </p>

      {painel?.modo === "criar" || painel?.modo === "editar" || painel?.modo === "nova-vigencia" ? (
        <Painel
          titulo={
            painel.modo === "criar"
              ? "Nova regra tributária"
              : painel.modo === "editar"
                ? `Editar ${painel.regra?.codigo}`
                : `Nova vigência de ${painel.regra?.codigo}`
          }
          descricao={
            painel.modo === "criar"
              ? "A regra nasce provisória. Validar é um ato separado, do responsável fiscal."
              : undefined
          }
          aoFechar={() => setPainel(null)}
        >
          <FormularioRegra
            modo={painel.modo}
            regra={painel.regra}
            aoConcluir={() =>
              concluir(
                painel.modo === "criar"
                  ? "Regra criada com status provisório."
                  : painel.modo === "editar"
                    ? "Regra atualizada."
                    : "Nova vigência aberta. A anterior foi encerrada e permanece no histórico.",
              )
            }
            aoCancelar={() => setPainel(null)}
          />
        </Painel>
      ) : null}

      {painel?.modo === "validar" && painel.regra ? (
        <Painel
          titulo={`Validar ${painel.regra.codigo}`}
          aoFechar={() => setPainel(null)}
        >
          <FormularioValidacao
            regra={painel.regra}
            aoConcluir={() =>
              concluir("Regra validada. Cotações passam a poder ser definitivas.")
            }
            aoCancelar={() => setPainel(null)}
          />
        </Painel>
      ) : null}

      {painel?.modo === "encerrar" && painel.regra ? (
        <Painel
          titulo={`Encerrar ${painel.regra.codigo}`}
          aoFechar={() => setPainel(null)}
        >
          <FormularioEncerramento
            regra={painel.regra}
            aoConcluir={() =>
              concluir("Vigência encerrada. A regra continua no histórico.")
            }
            aoCancelar={() => setPainel(null)}
          />
        </Painel>
      ) : null}
    </>
  );
}

function FormularioValidacao({
  regra,
  aoConcluir,
  aoCancelar,
}: {
  regra: RegraTributaria;
  aoConcluir: () => void;
  aoCancelar: () => void;
}) {
  const [validadoPor, setValidadoPor] = React.useState("");
  const [observacao, setObservacao] = React.useState("");
  const [erro, setErro] = React.useState<string | null>(null);
  const [salvando, setSalvando] = React.useState(false);

  async function enviar(evento: React.FormEvent) {
    evento.preventDefault();
    setSalvando(true);
    try {
      await api.post(`/tributario/regras/${regra.id}/validar`, {
        validado_por: validadoPor,
        observacao: observacao || null,
      });
      aoConcluir();
    } catch (e) {
      setErro(e instanceof ErroApi ? e.message : String(e));
    } finally {
      setSalvando(false);
    }
  }

  return (
    <form onSubmit={enviar} className="space-y-5">
      <Alerta severidade="atencao" titulo="Validar é assumir responsabilidade">
        Ao validar, esta regra passa a sustentar cotações definitivas. Seu nome e
        a data ficam registrados nela. Confira alíquota, base, tratamento e
        fundamento legal antes de continuar.
      </Alerta>

      <dl className="space-y-2 rounded-lg border border-borda p-4 text-sm">
        <div className="flex justify-between gap-4">
          <dt className="text-texto-suave">Tributo e operação</dt>
          <dd>
            {regra.tributo} · {rotulo(regra.tipo_operacao)}
          </dd>
        </div>
        <div className="flex justify-between gap-4">
          <dt className="text-texto-suave">Alíquota</dt>
          <dd className="numerico">
            {regra.aliquota ? percentual(regra.aliquota) : "por faixa"}
          </dd>
        </div>
        <div className="flex justify-between gap-4">
          <dt className="text-texto-suave">Vigência</dt>
          <dd>{vigencia(regra.vigencia_inicio, regra.vigencia_fim)}</dd>
        </div>
        <div className="flex justify-between gap-4">
          <dt className="text-texto-suave">Fundamento</dt>
          <dd className="max-w-xs text-right">{regra.fundamento_legal}</dd>
        </div>
      </dl>

      {erro ? (
        <Alerta severidade="critico" titulo="Não foi possível validar">
          {erro}
        </Alerta>
      ) : null}

      <Campo rotulo="Validado por" dica="Nome do responsável fiscal ou contábil">
        <Entrada
          required
          value={validadoPor}
          onChange={(e) => setValidadoPor(e.target.value)}
        />
      </Campo>
      <Campo rotulo="Observação (opcional)">
        <Entrada value={observacao} onChange={(e) => setObservacao(e.target.value)} />
      </Campo>

      <div className="flex justify-end gap-2 border-t border-borda pt-4">
        <Botao type="button" variante="secundario" onClick={aoCancelar}>
          Cancelar
        </Botao>
        <Botao type="submit" disabled={salvando}>
          {salvando ? "Validando…" : "Validar regra"}
        </Botao>
      </div>
    </form>
  );
}

function FormularioEncerramento({
  regra,
  aoConcluir,
  aoCancelar,
}: {
  regra: RegraTributaria;
  aoConcluir: () => void;
  aoCancelar: () => void;
}) {
  const [fim, setFim] = React.useState(new Date().toISOString().slice(0, 10));
  const [motivo, setMotivo] = React.useState("");
  const [erro, setErro] = React.useState<string | null>(null);
  const [salvando, setSalvando] = React.useState(false);

  async function enviar(evento: React.FormEvent) {
    evento.preventDefault();
    setSalvando(true);
    try {
      await api.post(`/tributario/regras/${regra.id}/encerrar`, {
        vigencia_fim: fim,
        motivo,
      });
      aoConcluir();
    } catch (e) {
      setErro(e instanceof ErroApi ? e.message : String(e));
    } finally {
      setSalvando(false);
    }
  }

  return (
    <form onSubmit={enviar} className="space-y-5">
      <Alerta severidade="info" titulo="A regra continua no histórico">
        Encerrar define a data em que a regra deixa de valer. Operações
        anteriores a essa data continuam sendo calculadas com ela — é o que
        mantém as cotações antigas reproduzíveis.
      </Alerta>

      {erro ? (
        <Alerta severidade="critico" titulo="Não foi possível encerrar">
          {erro}
        </Alerta>
      ) : null}

      <Campo rotulo="Último dia de vigência">
        <Entrada
          type="date"
          required
          value={fim}
          onChange={(e) => setFim(e.target.value)}
        />
      </Campo>
      <Campo rotulo="Motivo" dica="Ex.: benefício revogado, alteração de legislação">
        <Entrada required value={motivo} onChange={(e) => setMotivo(e.target.value)} />
      </Campo>

      <div className="flex justify-end gap-2 border-t border-borda pt-4">
        <Botao type="button" variante="secundario" onClick={aoCancelar}>
          Cancelar
        </Botao>
        <Botao type="submit" variante="perigo" disabled={salvando}>
          {salvando ? "Encerrando…" : "Encerrar vigência"}
        </Botao>
      </div>
    </form>
  );
}
