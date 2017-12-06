#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2017/12/4 15:25
# @Author  : Zoe
# @Site    : 
# @File    : FTRL2.py
# @Software: PyCharm Community Edition

import numpy as np

from datetime import datetime

from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score
from sklearn.base import BaseEstimator
from scipy.sparse import issparse


def slice_X(X, start=None, stop=None):
    if type(X) == list:
        if hasattr(start, '__len__'):
            return [x[start] for x in X]
        else:
            return [x[start:stop] for x in X]
    else:
        if hasattr(start, '__len__'):
            return X[start]
        else:
            return X[start:stop]


def make_batches(size, batch_size):
    nb_batch = int(np.ceil(size / float(batch_size)))
    return [(i * batch_size, min(size, (i + 1) * batch_size)) for i in range(0, nb_batch)]


class FtrlClassifier:
    def get_fans(self, shape):
        fan_in = shape[0] if len(shape) == 2 else np.prod(shape[1:])
        fan_out = shape[1] if len(shape) == 2 else shape[0]
        return fan_in, fan_out

    def uniform(self, shape, scale=0.05):
        return np.random.uniform(low=-scale, high=scale, size=shape)

    def glorot_uniform(self, shape):
        fan_in, fan_out = self.get_fans(shape)
        s = np.sqrt(6. / (fan_in + fan_out))
        return self.uniform(shape, s)

    def binary_entropy(self, p, y):
        loss = -(np.array(y) * np.log(p) + (1.0 - np.array(y)) * np.log(1.0 - np.array(p)))
        loss_out = np.zeros(len(y))
        return np.mean(loss)

    def get_weights(self):
        return self.w

    def get_z(self):
        return self.z

    def __init__(self, X, alpha=0.005, beta=1, decay=0, l1=0.0, l2=0.0, nb_epoch=5000, batch_size=128):
        # parameters
        self.alpha = alpha
        self.beta = beta
        self.l1 = l1
        self.l2 = l2
        self.nb_epoch = nb_epoch
        self.iterations = 0
        self.batch_size = batch_size
        self.decay = decay
        self.g = 0.
        # feature related parameters
        # model
        # n: squared sum of past gradients
        # z: weights
        # w: lazy weights
        self.input_size = X.shape[1]
        self.z = np.random.random(self.input_size)
        self.n = np.random.random(self.input_size)
        self.w = np.random.random(self.input_size)
        self.loss = 0.
        self.count = 0

    def fit(self, X, y, verbose=1, shuffle=False, validation_set=None):
        if self.z == None and self.n == None and self.w == None:
            self.input_size = X.shape[1]
            self.z = np.zeros(self.input_size)
            self.n = np.zeros(self.input_size)
            self.w = np.zeros(self.input_size)
        batch_size = self.batch_size
        preds = []
        sample_size = X.shape[0]
        index_array = np.arange(sample_size)
        for epoch in range(self.nb_epoch):
            if shuffle:
                np.random.shuffle(index_array)
            batches = make_batches(sample_size, batch_size)

            for batch_index, (batch_start, batch_end) in enumerate(batches):
                batch_ids = index_array[batch_start:batch_end]
                ins_batch = slice_X(X, batch_ids)
                outs = self.predict(ins_batch)
                if type(outs) != list:
                    outs = [outs]
                target = y[batch_ids]
                self.update(ins_batch, outs, target)
            if verbose >= 1:
                self.loss = self.binary_entropy(self.predict(X), y)
                if validation_set:
                    validation_loss = self.binary_entropy(self.predict(validation_set[0]), validation_set[1])
                    validation_auc = roc_auc_score(validation_set[1], self.predict(validation_set[0]))
                    print('eoch %s\tcurrent_loss: %f\tvalid_loss: %f\tvalid_auc: %f' % (
                    epoch, self.loss, validation_loss, validation_auc))
                else:
                    print('eoch %s\tcurrent loss: %f' % (epoch, self.loss))

    def predict(self, X):
        preds = []
        for x in X:
            p = self._predict(x)
            preds.append(p)
        return preds

    def predict_proba(self, X):
        return self.predict(X)

    def _predict(self, x):
        ''' Get probability estimation on x

            INPUT:
                x: features

            OUTPUT:
                probability of p(y = 1 | x; W)
        '''
        # parameters
        w = self.get_weights()
        # wTx is the inner product of w and x'

        if issparse(x):
            wTx = x.dot(w)[0]
        else:
            wTx = np.dot(x, w)
        # cache the current w for update stage
        self.w = w
        p = 1. / (1. + np.exp(-max(min(wTx, 35.), -35.)))
        # bounded sigmoid function, this is the probability estimation
        return p

    def sigmoid(self, inX):
        return 1.0 / (1 + np.exp(-inX))

    def bounded_sigmoid(self, inX):
        return 1. / (1. + np.exp(-max(min(wTx, 35.), -35.)))

    def update(self, x, p, y):
        ''' Update model using x, p, y

            INPUT:
                x: feature, a list of indices
                p: click probability prediction of our model
                y: answer

            MODIFIES:
                self.n: increase by squared gradient
                self.z: weights
        '''
        # gradient under logloss
        # if input is sparse
        if issparse(x):
            self.g = (p - y) * x
        else:
            self.g = np.dot((p - y), x)
        self.alpha += self.decay * self.iterations
        # update z and n
        # print self.g
        sigma = (np.sqrt(self.n + self.g * self.g) - np.sqrt(self.n)) / self.alpha
        self.z += self.g - sigma * self.w
        self.n += self.g * self.g
        self.iterations += 1
        w = (np.sign(self.z) * self.l1 - self.z) / ((self.beta + np.sqrt(self.n)) / self.alpha + self.l2)
        idx_0 = np.abs(self.z) <= self.l1
        w[idx_0] = 0
        self.w = w

if __name__ == '__main__':
    import matplotlib.pyplot as plt
    from sklearn.linear_model import LogisticRegression

    def iris_type(s):
        it = {b'Iris-setosa': 0, b'Iris-versicolor': 1, b'Iris-virginica': 2}
        return it[s]
    # 路径，浮点型数据，逗号分隔，第4列使用函数iris_type单独处理
    data = np.loadtxt('iris.data', dtype=float, delimiter=',', converters={4: iris_type})
    data=data[:99]
    # 将数据的0到3列组成x，第4列得到y
    x, y = np.split(data, (4,), axis=1)
    x = x[:, :2]

    logreg = FtrlClassifier(x)  # Logistic回归模型
    print(logreg.w)
    # logreg = BayesianLogisticRegressor()
    # for corpus in zip(x, y.ravel()):
    #     print (corpus)
    logreg.fit(x, y.ravel())  # 根据数据[x,y]，计算回归参数
    print ("Training Done!")
    # 画图
    N, M = 500, 500  # 横纵各采样多少个值
    x1_min, x1_max = x[:, 0].min(), x[:, 0].max()  # 第0列的范围
    x2_min, x2_max = x[:, 1].min(), x[:, 1].max()  # 第1列的范围
    t1 = np.linspace(x1_min, x1_max, N)
    t2 = np.linspace(x2_min, x2_max, M)
    x1, x2 = np.meshgrid(t1, t2)  # 生成网格采样点
    x_test = np.stack((x1.flat, x2.flat), axis=1)  # 测试点

    # # 无意义，只是为了凑另外两个维度
    # x3 = np.ones(x1.size) * np.average(x[:, 2])
    # x4 = np.ones(x1.size) * np.average(x[:, 3])
    # x_test = np.stack((x1.flat, x2.flat, x3, x4), axis=1)  # 测试点
    #
    y_hat = logreg.predict(x_test)  # 预测值
    y_hat = (np.array(y_hat) > 0.5).astype('int')
    y_hat = np.array(y_hat).reshape(x1.shape)  # 使之与输入的形状相同
    plt.pcolormesh(x1, x2, y_hat, cmap=plt.cm.Spectral,
                   alpha=0.1)  # 预测值的显示Paired/Spectral/coolwarm/summer/spring/OrRd/Oranges
    plt.scatter(x[:, 0], x[:, 1], c=y, edgecolors='k', cmap=plt.cm.prism)  # 样本的显示
    plt.xlabel('Sepal length')
    plt.ylabel('Sepal width')
    plt.xlim(x1_min, x1_max)
    plt.ylim(x2_min, x2_max)
    plt.grid()
    plt.show()

    # 训练集上的预测结果
    one = np.ones([len(x), 1])

    y_hat = logreg.predict(x)
    y = y.reshape(-1)  # 此转置仅仅为了print时能够集中显示

    y_hat=(np.array(y_hat)>0.5).astype('int')
    result = (y_hat == y)  # True则预测正确，False则预测错误
    print(y_hat)
    print(y)
    print(result)

    c = np.count_nonzero(result)  # 统计预测正确的个数
    print(c)
    print('Accuracy: %.2f%%' % (100 * float(c) / float(len(result))))
