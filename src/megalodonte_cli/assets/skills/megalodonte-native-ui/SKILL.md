---
name: megalodonte-native-ui
description: Criar ou refatorar interfaces Megalodonte com composição declarativa e State; aplicar as APIs específicas de desktop, Android ou Roku.
---

# Interface Megalodonte

Esta skill é compartilhada entre projetos desktop, Android e Roku. A composição declarativa, o tema e a separação de lógica orientam todas as plataformas. As regras abaixo que citam JavaFX, `megalodonte-components` ou `disgust-components` são específicas de desktop. No Android, adapte estado e composição às APIs da bridge; na Roku, use `megalodonte-roku` (inclusive seu `Counter` de runtime), sem presumir que `State` ou componentes desktop estejam disponíveis. Consulte o código da plataforma antes de aplicar uma API citada abaixo.

Construa a árvore de componentes de forma declarativa. `render()` e as fábricas de componentes retornam a expressão composta, com `children(...)` ou APIs reativas da biblioteca. Não monte uma árvore por etapas com variáveis de componentes, `getChildren().add(...)` ou `clear()` para depois retorná-la. Uma variável local pode representar um valor ou uma condição; não deve ser o mecanismo normal de montagem da UI.

```java
private final State<String> nome = State.of("");

@Override public Component render() {
    return new Column(new ColumnProps().spacingOf(12)).children(
        new Text("Nome"),
        new Input(nome, new InputProps().placeHolder("Digite o nome"))
    );
}
```

Declare `State`, `ListState` e estados derivados como campos no topo da classe dona do estado, antes dos métodos. Não crie `State` dentro de `render()` ou de fábricas chamadas pela renderização: uma nova renderização perderia o valor e as inscrições. Se a tela acumular muitos estados, cálculos, carregamento ou ações, transfira essa lógica para uma `ViewModel`; a tela recebe a ViewModel e apenas descreve a árvore. Use binding e componentes reativos para mudanças de dados e coleções, em vez de alterar manualmente os filhos da árvore.

Não chame `getJavaFxNode()` em código de aplicativo, inclusive para estilo, foco, seleção, eventos, tamanho ou inserção de filhos. Não instancie `javafx.scene.control` nem `javafx.scene.layout` em telas. Se a API de um componente não expõe uma operação necessária, avalie a possibilidade de expressá-la com `State` ou `Props`; se faltar uma capacidade reutilizável, implemente-a na biblioteca e consuma a nova API. JavaFX permanece dentro das bibliotecas como detalhe de implementação.

Para abrir links externos no navegador, use `megalodonte.base.Redirect.to(url)` ou `Redirect.to(url, onError)`. Não use `Desktop.getDesktop().browse(...)`, `URI.create(...)` nem crie threads na tela para essa finalidade; `Redirect` já encapsula a abertura assíncrona. O callback de erro é executado fora da thread de UI: se ele apresentar um alerta ou atualizar estado visual, encaminhe essa parte por `UI.runOnUi(...)`.

Use os valores e padrões do tema via `ThemeManager` e `Props`. Preserve as cores padrão dos componentes sempre que possível. Uma identidade visual realmente exclusiva, como marca, pode ter tokens próprios no tema do aplicativo; evite hexadecimais e CSS inline espalhados pelas telas. Quando uma opção de estilo ou tamanho é recorrente, modele-a em `Props` ou num componente reutilizável.

Não guarde `Column`, `Row`, `Container`, `Stack` ou outro componente como campo da tela. Se uma operação imperativa for realmente inevitável e não puder ser modelada por estado, guarde `Ref<T>` como campo e vincule a referência ao componente criado na árvore. `Ref` é exceção para casos como foco; não é substituto de `State` nem justificativa para manter uma árvore mutável.

Coloque composições reutilizáveis em uma classe `Components` com métodos de fábrica `static` que recebem estado, dados e callbacks e **retornam** o componente pronto. Não mantenha componentes mutáveis globais nessa classe. Separe lógica de domínio, serviços e ViewModel da composição da UI.

Quando a UI expõe uma sintaxe, ação ou estado pouco óbvio, explique-a junto ao controle com texto ou tooltip. Tooltips devem esclarecer o efeito do controle no contexto atual, sem substituir um exemplo completo no README. Confira a interface com os dados realmente carregados; a existência de um fluxo no repositório não demonstra que ele aparece na tela. Ao compartilhar recursos entre desktop e Android, compare os valores de tema e configuração efetivamente usados nas duas plataformas, respeitando as APIs de cada uma.

Modele a interface a partir do estado real: uma ação iniciar/parar deve ter um único controle que muda de rótulo e função; painéis de seleção e espaços reservados devem aparecer apenas quando há conteúdo utilizável, e uma única peça deve aproveitar a largura disponível. Quando uma operação demorada acontece, exponha progresso, sucesso e falha no aplicativo e nos logs da execução por terminal. Configurações que alteram processamento devem persistir e ser lidas tanto na prévia quanto na saída final; verifique os dois caminhos.


Antes de adicionar um componente, procure equivalentes em `megalodonte-components` e `disgust-components` e confira a API atual no código-fonte. Componentes gerais de layout, entrada e dados pertencem a `megalodonte-components`; identidade visual e controles específicos de Disgust pertencem a `disgust-components`. Crie a peça faltante na biblioteca adequada e use-a na aplicação. Preserve o comportamento e os dados existentes durante uma refatoração.

Ao alterar código de uma biblioteca, rode seus testes e `./gradlew publishToMavenLocal` no repositório dela; depois valide o aplicativo consumidor. `includeBuild` permite testar a fonte local, mas não atualiza o artefato que outros projetos obtêm de `mavenLocal()`. Publicação remota e `git push` seguem suas próprias autorizações e regras do workspace.

Depois de concluir uma alteração e obter sucesso nos testes pertinentes, faça commit nos repositórios alterados quando as regras de Git do workspace permitirem. Para bibliotecas, publique primeiro em Maven Local e valide os consumidores afetados; só então faça o commit. Confira o diff e o status de cada repositório para não incluir mudanças alheias. Commit local não autoriza `git push`: respeite as restrições de horário e a autorização de envio aplicáveis.

Ao corrigir um campo ou componente, busque usos equivalentes no aplicativo e nos consumidores relevantes e corrija o mesmo defeito onde ele ocorrer. Compare o significado dos dados antes de aplicar uma máscara indiscriminadamente: quantidade, valor monetário e medidas podem exigir escalas diferentes. Valide todos os usos afetados.

Em campos brasileiros formatados, use `pack.utilities.FormatterPack` como fonte das máscaras (CPF, CNPJ, CPF/CNPJ, CEP, telefone e moeda) por meio dos componentes existentes. Se faltar um campo reutilizável, implemente-o na biblioteca adequada usando o mesmo `FormatterPack`, em vez de duplicar a máscara na tela. Confira o contrato do `State`: alguns componentes guardam o valor sem pontuação, e `InputColumnCurrency` guarda centavos. Adapte o valor ao modelo de domínio quando necessário, sem alterar silenciosamente seu significado.

Antes de concluir, revise os arquivos de tela em busca de `getJavaFxNode`, `getChildren().add`, controles JavaFX nativos, CSS inline, `State.of` dentro de `render()` e campos de componentes. Se algum caso excepcional permanecer, explique-o explicitamente e não declare a tela conforme ao padrão.
