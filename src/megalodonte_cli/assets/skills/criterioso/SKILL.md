---
name: criterioso
description: Investigar, implementar e validar mudanças de software de ponta a ponta, especialmente quando há múltiplos projetos, geradores, bibliotecas ou ambientes.
---

# Desenvolvimento criterioso

Use esta skill em tarefas de manutenção e evolução de software. Preserve o objetivo e as restrições do usuário; não transforme um exemplo de um produto em regra universal. Aplique as verificações pertinentes ao risco e à mudança, sem criar cerimônias desnecessárias.

Quando um pedido acumula correções e complementos, mantenha uma lista curta dos resultados exigidos e confira cada um antes de encerrar. Uma resposta anterior ou um commit não prova que a etapa atual foi concluída; não deixe requisitos implícitos, como a aplicação já aberta ou o artefato consumido, fora da validação.

## Uso eficiente de contexto

Quando o plugin context-mode estiver disponível, use suas ferramentas de execução e busca para analisar saídas extensas, logs, testes, documentação e dados, trazendo ao contexto somente os trechos e resultados necessários. Para várias consultas ao mesmo material, prefira indexar e pesquisar de forma direcionada. Respeite as permissões da sessão e evite indexar segredos ou dados privados sem necessidade; não execute ações externas não autorizadas. Não afirme que usou o plugin ou obteve economia medida sem confirmação. Se as ferramentas não estiverem disponíveis, use buscas específicas, limite saídas e processe dados localmente, sem perder diagnósticos ou verificações relevantes. Economia de tokens não reduz a cobertura necessária nem substitui a documentação do trabalho.

## Investigar o alvo real

Antes de alterar código, identifique o arquivo, versão, processo e projeto que o usuário está usando. Confira o caminho aberto pela aplicação e, antes de commit ou push, `git rev-parse --show-toplevel` e o remoto. Compare cópias geradas, checkouts e dados locais; não conclua que uma mudança aparece na interface apenas porque existe no repositório que você editou. Não crie um clone nem substitua ou remova dados locais por suposição. Ao corrigir uma divergência, deixe explícita uma única fonte de verdade e preserve o que é próprio de cada ambiente.

Reproduza ou rastreie o cenário descrito, inclusive a sequência de cliques, entrada, estado salvo e saída. Busque a causa no caminho completo antes de modificar a primeira função suspeita. Quando o usuário informa que uma correção não funcionou, trate a observação como evidência nova: confira a versão efetivamente carregada, caches, artefatos publicados e outros pontos do mesmo fluxo antes de afirmar que o defeito persiste no código.

## Implementar no lugar certo

Separe mecanismos genéricos de regras do produto. Um editor ou gerador não deve esconder comandos, respostas e decisões que pertencem ao projeto gerado. Alterar o gerador não atualiza automaticamente projetos existentes: ajuste o projeto em uso e o gerador quando ambos fazem parte do objetivo. Migre a lógica completa, com estado e testes relevantes, antes de remover o código antigo; verifique que o empacotamento inclui os arquivos e APIs necessários.

Procure usos equivalentes do comportamento defeituoso e corrija os afetados, respeitando diferenças de domínio. Prefira bibliotecas e componentes existentes, verificando a API real antes de usá-la. Ao mudar uma biblioteca consumida localmente, execute seus testes, publique em Maven Local quando esse for o mecanismo de consumo, e confira o artefato atualizado no projeto-alvo. Não rode novamente testes de outras aplicações sem pedido explícito do usuário. `includeBuild` e compilação da fonte não provam que o aplicativo instalado recebeu a mudança.

## Validar o resultado observável

Teste apenas o projeto alterado e o menor percurso que demonstra o requisito: entrada, ação, persistência, reabertura e resultado visível. Para prévia e exportação, confirme que ambas usam o mesmo estado. Para CLI, teste defaults, opções disponíveis e término de entrada multiline. Para integrações, valide o evento e o destino sem afirmar entrega quando só a chamada local foi testada. Respeite restrições do usuário, como não iniciar uma exportação demorada.

Uma compilação bem-sucedida é evidência de compilação, não de comportamento. Quando o teste real não for possível, declare exatamente o que foi validado e o que resta. Não diga “tudo aparece”, “está funcionando” ou “foi entregue” sem verificar a instância, o projeto e o resultado correspondentes. Se houver falha, explique a causa encontrada e continue o trabalho autorizado em vez de encerrar com uma correção parcial.

## Documentação contínua do projeto

Em toda mudança de software, atualize proativamente a documentação pertinente no próprio projeto, sem esperar solicitação: registre o estado real, as decisões e trade-offs, a forma de uso, os próximos passos e quaisquer limitações em `docs/CONTEXT.md`, `docs/DECISIONS.md` e `docs/TODO.md` quando esses arquivos fizerem parte da convenção do projeto. Atualize também o README ou a documentação pública quando o uso mudar. Preserve o conteúdo existente, evite repetir informações sem necessidade e nunca descreva uma proposta ou implementação parcial como concluída.

## Tornar o recurso utilizável e entregar

Recursos com sintaxe ou sequência não óbvia precisam de um exemplo de uso no README do projeto em uso e, se forem reutilizáveis, no modelo gerado. Na interface, use texto ou tooltip junto ao controle para explicar a ação; mostre o caminho entre clique, gatilho e resposta. Operações longas devem expor progresso, sucesso e erro também nos logs relevantes. Revise documentos antigos que contradigam o comportamento novo.

### README público e documentação interna

Trate o README como a entrada de quem encontrou **apenas aquele repositório**. Comece pelo nome, propósito e estado real do produto; mostre suas funções principais, requisitos, instalação, primeiro uso e links para a documentação detalhada. Prefira exemplos executáveis e caminhos relativos à raiz do próprio repositório ou variáveis de ambiente documentadas. Um caminho absoluto do computador do autor, um checkout irmão presumido, um token, um ID privado ou instruções dirigidas ao agente não pertencem ao README. Mova decisões, migrações, notas de manutenção e instruções específicas do workspace para `docs/`, `CONTRIBUTING.md` ou `AGENTS.md`, conforme o público.

Use identidade visual com medida: inclua logotipo, ícone ou capturas **reais e versionadas** quando existirem e ajudarem a reconhecer ou usar o produto; escreva texto alternativo e verifique os links relativos no GitHub. Não tire novas capturas de tela da aplicação, mesmo para documentação ou conferência visual, salvo pedido explícito do usuário. Use capturas já fornecidas ou versionadas quando forem úteis. Não use imagem gerada como se fosse captura, não exponha dados pessoais ou credenciais e não acrescente espaços reservados vazios. Bibliotecas e ferramentas de terminal podem ser melhor explicadas por exemplos curtos de entrada e saída ou diagramas; não precisam de screenshots artificiais. Se ainda não houver captura adequada, registre a pendência em documentação de manutenção sem fingir que ela existe.

Quando o usuário fornecer anexos que sejam úteis como referência de desenvolvimento ou documentação, copie os arquivos pertinentes para dentro do projeto, em uma pasta de documentação ou recursos com nomes descritivos, e faça links relativos no documento que os utiliza. Verifique se os arquivos copiados abrem e se não contêm segredos ou dados privados indevidos antes de versioná-los. Não deixe a única cópia em caminhos temporários, anexos da conversa ou diretórios particulares da máquina do autor.

Ao atualizar muitos repositórios, faça inventário antes: identifique o público, o comando de execução verdadeiro, as imagens rastreadas pelo Git, links quebrados e trechos dependentes do computador do autor. Melhore cada README conforme seu produto, sem copiar a mesma estrutura ou marketing para todos. Confira a renderização Markdown, os caminhos dos recursos e os comandos apresentados; quando um gerador cria projetos, corrija também seu modelo de README e teste a saída gerada.

Antes de concluir, revise o diff e o status de cada repositório alterado, rode apenas as verificações do projeto modificado e respeite as regras locais de commit e push. Commit, publicação local de biblioteca e push são ações distintas; não presuma autorização de uma a partir da outra. Relate o que mudou, a evidência da validação e qualquer limite material, sem apresentar uma intenção ou um teste indireto como resultado concluído.
