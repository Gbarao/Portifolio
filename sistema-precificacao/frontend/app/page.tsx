import Link from "next/link";
import {
  Boxes,
  Calculator,
  ChartNoAxesCombined,
  Factory,
  Landmark,
} from "lucide-react";

import { CabecalhoPagina } from "@/components/layout/pagina";
import { Cartao, CartaoCorpo, Distintivo } from "@/components/ui/primitivos";

const MODULOS = [
  {
    titulo: "Cadastros",
    descricao:
      "Materiais com rendimento e faixas de qualidade, parceiros com regime fiscal e prazos, parâmetros por vigência.",
    href: "/cadastros/materiais",
    Icone: Boxes,
    disponivel: true,
  },
  {
    titulo: "Operações",
    descricao:
      "Lotes de compra, tickets de balança, qualidade, saídas e perdas. Resultado do lote com memória de cálculo.",
    href: "/operacoes/lotes",
    Icone: Factory,
    disponivel: true,
  },
  {
    titulo: "Motor tributário",
    descricao:
      "Matriz de regras versionadas por vigência, validação pelo responsável fiscal e alerta de faixa do Simples.",
    href: "/tributario/regras",
    Icone: Landmark,
    disponivel: true,
  },
  {
    titulo: "Cotações e simulação",
    descricao:
      "Escada de cinco preços, avaliação de proposta por alçada, cenários e preço máximo de compra.",
    href: "/cotacoes",
    Icone: Calculator,
    disponivel: true,
  },
  {
    titulo: "Painel gerencial",
    descricao:
      "Margem por dimensão, ponte de margem, ociosidade, ciclo financeiro e créditos tributários.",
    href: "/painel",
    Icone: ChartNoAxesCombined,
    disponivel: true,
  },
];

export default function Inicio() {
  return (
    <>
      <CabecalhoPagina
        titulo="Sistema de custeio e precificação"
        descricao="Custeio híbrido por lote, ABC e absorção gerencial, com motor tributário parametrizável por regime e escada de cinco preços."
      />

      <div className="grid gap-4 sm:grid-cols-2">
        {MODULOS.map((modulo) => {
          const conteudo = (
            <Cartao
              className={
                modulo.disponivel
                  ? "h-full transition-shadow hover:shadow-md"
                  : "h-full opacity-60"
              }
            >
              <CartaoCorpo className="space-y-3">
                <div className="flex items-start justify-between gap-3">
                  <span className="flex size-9 items-center justify-center rounded-lg bg-marca-50 text-marca-700">
                    <modulo.Icone className="size-4.5" aria-hidden />
                  </span>
                  {!modulo.disponivel ? (
                    <Distintivo tom="neutro">Passo 6</Distintivo>
                  ) : null}
                </div>
                <div>
                  <h2 className="text-sm font-semibold">{modulo.titulo}</h2>
                  <p className="mt-1 text-sm text-texto-suave">{modulo.descricao}</p>
                </div>
              </CartaoCorpo>
            </Cartao>
          );

          return modulo.disponivel ? (
            <Link key={modulo.titulo} href={modulo.href} className="block">
              {conteudo}
            </Link>
          ) : (
            <div key={modulo.titulo}>{conteudo}</div>
          );
        })}
      </div>

      <Cartao className="mt-6">
        <CartaoCorpo className="space-y-2 text-sm text-texto-suave">
          <p className="font-medium text-texto">Três regras que o sistema não relaxa</p>
          <ul className="list-disc space-y-1 pl-5">
            <li>
              Nenhum preço aparece sem o rótulo da camada de custo que o gerou.
            </li>
            <li>
              Regra fiscal vencida ou provisória impede cotação definitiva, mesmo
              com todos os demais campos preenchidos.
            </li>
            <li>
              Crédito tributário condicionado não reduz custo antes da confirmação
              documental.
            </li>
          </ul>
        </CartaoCorpo>
      </Cartao>
    </>
  );
}
