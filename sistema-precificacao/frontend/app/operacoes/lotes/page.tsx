"use client";

import Link from "next/link";

import { CabecalhoPagina } from "@/components/layout/pagina";
import { StatusDadoBadge } from "@/components/dominio/indicadores";
import { ErroDeCarregamento } from "@/components/ui/estado-api";
import {
  Cartao,
  Distintivo,
  LinhaTabela,
  Tabela,
  Td,
  Th,
  Vazio,
} from "@/components/ui/primitivos";
import { useLista } from "@/lib/dados";
import { data, peso, precoUnitario, rotulo } from "@/lib/formato";
import type { Lote } from "@/lib/tipos";

const TOM_STATUS: Record<string, "ok" | "info" | "atencao" | "critico" | "neutro"> = {
  ABERTO: "info",
  EM_PROCESSAMENTO: "atencao",
  AGUARDANDO_APROVACAO: "atencao",
  FECHADO: "ok",
  BLOQUEADO: "critico",
};

export default function PaginaLotes() {
  const { dados, erro, carregando } = useLista<Lote>("/lotes?limite=100");
  const lotes = dados ?? [];

  if (erro) {
    return (
      <>
        <CabecalhoPagina titulo="Lotes de compra" />
        <ErroDeCarregamento erro={erro} />
      </>
    );
  }

  return (
    <>
      <CabecalhoPagina
        titulo="Lotes de compra"
        descricao="O lote é a unidade básica de rastreamento. Cada um carrega origem, pesagem, qualidade, processamento, saídas e perdas."
      />

      <Cartao className={carregando ? "opacity-60" : undefined}>
        {lotes.length === 0 && !carregando ? (
          <Vazio
            titulo="Nenhum lote registrado"
            descricao="Registre a entrada de material para acompanhar o balanço de massa e o resultado econômico."
          />
        ) : (
          <Tabela>
            <thead>
              <tr>
                <Th>Código</Th>
                <Th>Entrada</Th>
                <Th numerica>Quantidade</Th>
                <Th numerica>Preço de compra</Th>
                <Th>Status</Th>
                <Th>Dado</Th>
                <Th />
              </tr>
            </thead>
            <tbody>
              {lotes.map((lote) => (
                <LinhaTabela key={lote.id}>
                  <Td className="font-mono text-xs">{lote.codigo}</Td>
                  <Td className="text-texto-suave">{data(lote.data_entrada)}</Td>
                  <Td numerica>{peso(lote.quantidade_negociada_kg)}</Td>
                  <Td numerica>{precoUnitario(lote.preco_unitario_bruto)}</Td>
                  <Td>
                    <Distintivo tom={TOM_STATUS[lote.status] ?? "neutro"}>
                      {rotulo(lote.status)}
                    </Distintivo>
                  </Td>
                  <Td>
                    <StatusDadoBadge status={lote.status_dado} />
                  </Td>
                  <Td className="text-right">
                    <Link
                      href={`/operacoes/lote?id=${lote.id}`}
                      className="text-sm font-medium text-marca-700 hover:underline"
                    >
                      Resultado
                    </Link>
                  </Td>
                </LinhaTabela>
              ))}
            </tbody>
          </Tabela>
        )}
      </Cartao>
    </>
  );
}
