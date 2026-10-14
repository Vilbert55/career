# Kubernetes: памятка

Сквозной пример - тот же сервис `payments`, что в [docker.md](docker.md): образ собран, теперь его нужно запустить
в кластере в трех копиях, без простоя при обновлении.

**Содержание**

- [Зачем Kubernetes](#зачем-kubernetes)
- [Из чего состоит кластер](#из-чего-состоит-кластер)
- [Объекты](#объекты)
- [Сервис payments в манифестах](#сервис-payments-в-манифестах)
- [Пробы](#пробы)
- [Ресурсы](#ресурсы)
- [Обновление, откат, остановка пода](#обновление-откат-остановка-пода)
- [kubectl](#kubectl)
- [Что сломалось: статусы пода](#что-сломалось-статусы-пода)
- [Helm и OpenShift](#helm-и-openshift)

## Зачем Kubernetes

Docker запускает контейнеры на одной машине. Kubernetes запускает их на кластере машин и сам следит за ними:
- контейнер упал - перезапустит;
- узел умер - поднимет поды на других узлах;
- нужно больше копий - добавит и распределит по узлам;
- вышла новая версия - заменит копии по одной, без простоя.

Работа декларативная: описываешь в YAML желаемое состояние ("3 копии `payments:1.4.2`"), Kubernetes постоянно
сравнивает его с фактическим и исправляет разницу.

## Из чего состоит кластер

| Часть | Что делает |
|---|---|
| **API server** | единственная точка входа: `kubectl`, узлы и контроллеры общаются только через него |
| **etcd** | хранилище состояния кластера: все объекты |
| **scheduler** | выбирает, на какой узел поставить новый под |
| **controller manager** | циклы "желаемое против фактического": не хватает подов - создает |
| **kubelet** | агент на каждом узле: запускает контейнеры подов и проверяет пробы |
| **kube-proxy** | на каждом узле: направляет трафик Service к подам |

Первые четыре - управляющая часть (control plane), последние два - на рабочих узлах (nodes).

## Объекты

| Объект | Что это | Аналог в Docker |
|---|---|---|
| **Pod** | один или несколько контейнеров с общей сетью и томами. Минимальная единица. Смертен: взамен упавшего создается новый, с другим именем и IP | `docker run` |
| **Deployment** | держит N одинаковых подов, обновляет их по очереди, умеет откатывать | сервис в compose |
| ReplicaSet | создается Deployment'ом, держит число подов. Руками не трогают | - |
| **Service** | постоянное имя и IP перед группой подов, балансирует запросы между ними | имя сервиса в compose |
| **Ingress** | вход HTTP снаружи кластера: домен и путь ведут на Service | nginx перед сервисами |
| **ConfigMap** | настройки - в переменные окружения или файлы | `environment` в compose |
| **Secret** | пароли и токены. В base64, это кодирование, шифрованием оно не является | - |
| **Namespace** | папка для объектов: команда, контур | - |
| StatefulSet | поды с постоянными именами и своими дисками: базы, Kafka | - |
| DaemonSet | по поду на каждом узле: сбор логов, мониторинг | - |
| Job, CronJob | разовая задача; задача по расписанию | cron |
| PersistentVolumeClaim | заявка на постоянный диск | том |
| HorizontalPodAutoscaler | меняет число подов по нагрузке, например по CPU | - |

## Сервис payments в манифестах

`payments.yaml` - Deployment и Service:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: payments
spec:
  replicas: 3
  selector:
    matchLabels:
      app: payments              # каким подам Deployment хозяин
  strategy:
    rollingUpdate:
      maxSurge: 1                # при обновлении можно на 1 под больше
      maxUnavailable: 0          # и ни одного меньше: без простоя
  template:                      # шаблон пода
    metadata:
      labels:
        app: payments
    spec:
      containers:
        - name: payments
          image: registry.example.com/payments:1.4.2
          ports:
            - containerPort: 8000
          envFrom:
            - configMapRef:
                name: payments-config          # все ключи ConfigMap - переменные окружения
          env:
            - name: DATABASE_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: payments-secret
                  key: db-password
          resources:
            requests:            # гарантировано, по этому выбирается узел
              cpu: 250m          # четверть ядра
              memory: 256Mi
            limits:
              memory: 512Mi      # больше - контейнер убьют (OOMKilled)
          readinessProbe:        # готов принимать запросы?
            httpGet:
              path: /health
              port: 8000
            periodSeconds: 5
          livenessProbe:         # процесс жив?
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 10
            periodSeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: payments
spec:
  selector:
    app: payments                # направлять трафик подам с этой меткой
  ports:
    - port: 80                   # порт Service
      targetPort: 8000           # порт контейнера
```

- **Метки (labels) связывают все вместе.** Deployment создает поды с меткой `app: payments`, Service отправляет
  запросы подам с этой меткой. Опечатка в метке - Service без подов, запросы никуда не идут.
- Другие сервисы того же namespace обращаются по имени: `http://payments`. Из другого namespace -
  `http://payments.<namespace>.svc.cluster.local`.
- Типы Service: `ClusterIP` (по умолчанию) - только внутри кластера; `NodePort` - порт на каждом узле;
  `LoadBalancer` - внешний балансировщик облака. Снаружи по HTTP обычно заходят через Ingress.
- Применить: `kubectl apply -f payments.yaml`. Повторный `apply` с новым тегом образа - это и есть обновление.

## Пробы

| Проба | Вопрос | Если не прошла |
|---|---|---|
| **readiness** | готов принимать запросы? | под убирают из Service, трафик к нему не идет. Не перезапускают |
| **liveness** | процесс жив, не завис? | контейнер перезапускают |
| **startup** | приложение уже запустилось? | пока не прошла, две другие не проверяются. Не прошла за отведенное время - перезапуск |

- Без readiness трафик пойдет в под сразу после старта контейнера, когда приложение еще не готово.
- Liveness не должна проверять базу и другие внешние сервисы. База упала - liveness падает у всех подов,
  и Kubernetes перезапускает их по кругу, хотя дело не в них.
- Медленный старт (загрузка модели, прогрев кеша) - startup-проба, иначе liveness убьет под до готовности.

## Ресурсы

- **requests** - сколько гарантировано. По сумме requests scheduler выбирает узел, где хватит места.
- **limits** - потолок:
  - CPU выше лимита - процесс притормаживают (throttling), он работает медленнее;
  - память выше лимита - контейнер убивают, статус `OOMKilled`, затем перезапуск.
- Единицы: `cpu: 250m` - 250 милли-ядер, четверть ядра; `memory: 256Mi` - мебибайты.
- Requests не указаны - под может попасть на перегруженный узел. Нет лимита памяти - утечка в одном поде
  отнимает память у соседей по узлу.

## Обновление, откат, остановка пода

**Обновление (RollingUpdate).** Новый тег в манифесте и `kubectl apply`:
1. поднимается под новой версии;
2. как только он прошел readiness, он получает трафик, а один старый под удаляется;
3. так по одному, пока все поды не станут новыми.

Новая версия не проходит readiness - обновление застревает, старые поды продолжают работать.

```bash
kubectl rollout status deployment/payments    # дождаться окончания обновления
kubectl rollout history deployment/payments   # версии
kubectl rollout undo deployment/payments      # откатить на предыдущую
```

**Остановка пода** - при обновлении, масштабировании, переезде на другой узел:
1. одновременно под убирают из Service и шлют контейнеру `SIGTERM`;
2. ждут `terminationGracePeriodSeconds` (по умолчанию 30 с), затем `SIGKILL`.

Исключение пода из балансировки доходит до узлов не мгновенно, и первые секунды запросы еще идут. Поэтому часто
добавляют `preStop` с паузой в несколько секунд перед `SIGTERM`.

Приложение должно ловить `SIGTERM` и дорабатывать текущие запросы. Поэтому в Dockerfile exec-форма `CMD`:
в shell-форме сигнал до Python не доходит.

## kubectl

```bash
kubectl get pods                              # поды; -n <namespace> - в другом namespace, -o wide - с узлами
kubectl get deploy,svc,ingress                # несколько видов объектов сразу
kubectl describe pod <pod>                    # подробности и события (Events) - первое, куда смотреть
kubectl logs -f <pod>                         # логи; --previous - логи упавшего контейнера до перезапуска
kubectl exec -it <pod> -- sh                  # зайти в контейнер
kubectl apply -f payments.yaml                # создать или обновить по манифесту
kubectl delete -f payments.yaml
kubectl scale deployment payments --replicas=5
kubectl port-forward svc/payments 8000:80     # Service на localhost:8000 - отладка с ноутбука
kubectl top pods                              # потребление CPU и памяти
```

## Что сломалось: статусы пода

| Статус | Что значит | Где смотреть |
|---|---|---|
| `Pending` | под не встает на узел: ни на одном не хватает ресурсов под requests или нет подходящего узла | `describe pod`, Events |
| `ImagePullBackOff`, `ErrImagePull` | не скачать образ: неверный тег, нет доступа к реестру | `describe pod` |
| `CrashLoopBackOff` | контейнер стартует и падает, Kubernetes перезапускает его с растущей паузой | `logs --previous` |
| `OOMKilled` | превышен лимит памяти | `describe pod`, Last State |
| `CreateContainerConfigError` | нет ConfigMap или Secret, на которые ссылается под | `describe pod` |
| `Running`, но `READY 0/1` | readiness не проходит, трафик не идет | `describe pod`, логи |

## Helm и OpenShift

- **Helm** - менеджер пакетов Kubernetes. Чарт (chart) - шаблоны манифестов плюс `values.yaml` с параметрами:
  тег образа, число копий, ресурсы. Один чарт - разные `values` для dev, test и prod.
  Команды: `helm install`, `helm upgrade`, `helm rollback`.
- **OpenShift** - Kubernetes от Red Hat с добавками. `oc` вместо `kubectl`, команды те же. `Route` вместо
  `Ingress`, встроенная сборка образов, строже безопасность. Главное отличие для разработчика: контейнер
  запускается под случайным UID. Образ должен работать под любым пользователем, поэтому файлы приложения отдают
  группе 0: `chgrp -R 0 /app && chmod -R g=u /app`.
