/**
 * Formatacao para leitura humana.
 *
 * A API envia decimais como string em precisao cheia, de proposito: arredondar
 * no servidor quebraria a reprodutibilidade da memoria de calculo. O
 * arredondamento e decisao de apresentacao e mora aqui.
 */

const LOCALE = "pt-BR";

function paraNumero(valor: string | number | null | undefined): number {
  if (valor === null || valor === undefined || valor === "") return 0;
  return typeof valor === "number" ? valor : Number(valor);
}

export function moeda(valor: string | number | null | undefined, casas = 2): string {
  return new Intl.NumberFormat(LOCALE, {
    style: "currency",
    currency: "BRL",
    minimumFractionDigits: casas,
    maximumFractionDigits: casas,
  }).format(paraNumero(valor));
}

/** Preco unitario aceita mais casas: R$/kg costuma ter 4. */
export function precoUnitario(valor: string | number | null | undefined): string {
  return moeda(valor, 4);
}

export function numero(
  valor: string | number | null | undefined,
  casas = 2,
): string {
  return new Intl.NumberFormat(LOCALE, {
    minimumFractionDigits: casas,
    maximumFractionDigits: casas,
  }).format(paraNumero(valor));
}

/** Recebe fracao decimal (0,0925) e devolve percentual (9,25%). */
export function percentual(
  valor: string | number | null | undefined,
  casas = 2,
): string {
  return new Intl.NumberFormat(LOCALE, {
    style: "percent",
    minimumFractionDigits: casas,
    maximumFractionDigits: casas,
  }).format(paraNumero(valor));
}

export function peso(valorKg: string | number | null | undefined): string {
  const kg = paraNumero(valorKg);
  if (Math.abs(kg) < 1000) return `${numero(kg, 0)} kg`;

  // "12,000 t" e ambiguo na leitura; zeros a direita sao removidos para que
  // 12.000 kg apareca como "12 t" e 10.440 kg como "10,44 t".
  const toneladas = new Intl.NumberFormat(LOCALE, {
    minimumFractionDigits: 0,
    maximumFractionDigits: 3,
  }).format(kg / 1000);
  return `${toneladas} t`;
}

export function data(iso: string | null | undefined): string {
  if (!iso) return "—";
  const partes = iso.slice(0, 10).split("-");
  if (partes.length !== 3) return iso;
  return `${partes[2]}/${partes[1]}/${partes[0]}`;
}

export function vigencia(inicio: string, fim: string | null): string {
  return fim ? `${data(inicio)} a ${data(fim)}` : `desde ${data(inicio)}`;
}

/** Rotulo legivel para enums em CAIXA_ALTA_COM_UNDERSCORE. */
export function rotulo(valor: string | null | undefined): string {
  if (!valor) return "—";

  const palavras = valor.split("_").map((palavra, indice) => {
    // Numerais romanos dos anexos do Simples continuam em caixa alta:
    // "ANEXO_II" vira "Anexo II", nunca "Anexo ii".
    if (/^[IVX]+$/.test(palavra)) return palavra;
    const minuscula = palavra.toLowerCase();
    return indice === 0
      ? minuscula.charAt(0).toUpperCase() + minuscula.slice(1)
      : minuscula;
  });

  return palavras.join(" ");
}
